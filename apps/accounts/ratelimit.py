"""
Lightweight cache-based rate limiting for the login and register endpoints.

Uses Django's default cache (LocMemCache, no extra config needed) instead of
adding a dependency like django-axes. Good enough for a single-process
deployment; if the app later runs behind multiple gunicorn/uwsgi workers,
point CACHES at Redis/Memcached in settings.py so the counters are shared
across processes — LocMemCache state is per-process and won't work correctly
otherwise.
"""
from django.conf import settings
from django.core.cache import cache

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60  # 15 minutes

REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 60 * 60  # 1 hour

# How many login codes we'll email out for the same address in a row before
# making the requester wait — this is the guard against inbox-bombing a
# victim (or against an attacker using unlimited fresh codes to sidestep
# CODE_VERIFY_MAX_ATTEMPTS below, since every new code resets its own
# per-code attempt counter to zero).
CODE_REQUEST_MAX_ATTEMPTS = 3
CODE_REQUEST_WINDOW_SECONDS = 10 * 60  # 10 minutes

# How many wrong codes we'll accept for one *account* before locking it out
# — independent of the LoginCode row's own `attempts` field, and NOT reset
# by requesting a fresh code, so an attacker can't dodge it by just asking
# for a new code every few guesses.
CODE_VERIFY_MAX_ATTEMPTS = 20          # per ACCOUNT, all IPs together (anti code-farming)
CODE_VERIFY_IP_MAX_ATTEMPTS = 5        # per (IP, account): one attacker can't lock a victim out
CODE_VERIFY_LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _client_ip(request):
    """
    Real client IP, resistant to X-Forwarded-For spoofing.

    1. CLIENT_IP_HEADER (e.g. CF-Connecting-IP) if configured — only valid when
       the app is reachable exclusively through that proxy.
    2. Otherwise, when BEHIND_PROXY, take the entry TRUSTED_PROXY_COUNT hops from
       the RIGHT of X-Forwarded-For (the part our own proxies appended), never
       the leftmost one, which the client controls.
    3. Otherwise REMOTE_ADDR.
    """
    header = getattr(settings, "CLIENT_IP_HEADER", "")
    if header:
        value = request.META.get("HTTP_" + header.upper().replace("-", "_"), "").strip()
        if value:
            return value
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        parts = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        n = max(int(getattr(settings, "TRUSTED_PROXY_COUNT", 1)), 1)
        if len(parts) >= n:
            return parts[-n]
    return request.META.get("REMOTE_ADDR", "unknown")


def _login_key(request, identifier):
    return f"login_lock:{_client_ip(request)}:{identifier.lower()}"


def is_login_locked(request, identifier):
    return cache.get(_login_key(request, identifier), 0) >= LOGIN_MAX_ATTEMPTS


def register_login_failure(request, identifier):
    key = _login_key(request, identifier)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, LOGIN_LOCKOUT_SECONDS)
    return attempts


def clear_login_failures(request, identifier):
    cache.delete(_login_key(request, identifier))


def _register_key(request):
    return f"register_rate:{_client_ip(request)}"


def is_register_rate_limited(request):
    return cache.get(_register_key(request), 0) >= REGISTER_MAX_ATTEMPTS


def register_attempt(request):
    key = _register_key(request)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, REGISTER_WINDOW_SECONDS)
    return attempts


def _code_request_key(request, email):
    return f"code_request_rate:{_client_ip(request)}:{email.lower()}"


def is_code_request_rate_limited(request, email):
    return cache.get(_code_request_key(request, email), 0) >= CODE_REQUEST_MAX_ATTEMPTS


def register_code_request(request, email):
    key = _code_request_key(request, email)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, CODE_REQUEST_WINDOW_SECONDS)
    return attempts


def _code_verify_key(request, user_id):
    # Account-wide counter (all IPs). High threshold: it only exists to stop
    # distributed guessing, NOT to be reachable by a single attacker.
    return f"code_verify_lock:{user_id}"


def _code_verify_ip_key(request, user_id):
    # Per (IP, account) counter: low threshold. A single attacker hits this
    # first and only locks THEMSELVES out, not the real customer.
    return f"code_verify_lock_ip:{_client_ip(request)}:{user_id}"


def is_code_verify_locked(request, user_id):
    return (
        cache.get(_code_verify_ip_key(request, user_id), 0) >= CODE_VERIFY_IP_MAX_ATTEMPTS
        or cache.get(_code_verify_key(request, user_id), 0) >= CODE_VERIFY_MAX_ATTEMPTS
    )


def register_code_verify_failure(request, user_id):
    attempts = 0
    for key in (_code_verify_key(request, user_id), _code_verify_ip_key(request, user_id)):
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, CODE_VERIFY_LOCKOUT_SECONDS)
    return attempts


def clear_code_verify_failures(request, user_id):
    cache.delete(_code_verify_key(request, user_id))
    cache.delete(_code_verify_ip_key(request, user_id))


# --- WhatsApp/SMS gönderim limitleri (para harcayan işlem!) -----------------
# Her kod gönderimi Meta'ya ücret yazar. Aşağıdaki limitler, bir betiğin
# yüzlerce farklı numaraya (ya da tek bir kurbana) mesaj yağdırıp faturayı
# şişirmesini engeller. Sayaçlar IP'ye göre VE numaraya göre (tüm IP'ler
# toplamı) tutulur; numara anahtarı canonical_phone_key() ile üretilmelidir.
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_SEND_IP_MAX = 10
OTP_SEND_IP_WINDOW_SECONDS = 60 * 60
OTP_SEND_PHONE_MAX = 5
OTP_SEND_PHONE_WINDOW_SECONDS = 60 * 60


def _bump(key, window):
    if cache.add(key, 1, window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # anahtar tam bu sırada süresi doldu
        cache.set(key, 1, window)
        return 1


def otp_send_check(request, phone_key):
    """
    None  -> gönderime izin var (sayaçlar artırıldı).
    "cooldown" -> aynı numaraya 60 sn içinde zaten kod gönderilmiş.
    "limit"    -> IP / numara / günlük genel limit aşıldı.

    ÖNEMLİ: Sayaçlar yalnızca gönderime İZİN verildiğinde kalıcı artar.
    Bir limit aşıldığında o ana kadar artırılan her şey geri alınır; aksi
    halde tek bir IP, hiç mesaj gönderilmeden global günlük bütçeyi (ve
    kurbanın numara sayacını) tüketip herkesi kilitleyebilirdi.
    """
    cooldown_key = f"otp_cooldown:{phone_key}"
    if not cache.add(cooldown_key, 1, OTP_RESEND_COOLDOWN_SECONDS):
        return "cooldown"

    ip_key = f"otp_ip:{_client_ip(request)}"
    phone_counter_key = f"otp_phone:{phone_key}"
    daily_key = "otp_global_daily"
    daily_max = getattr(settings, "OTP_DAILY_GLOBAL_MAX", 500)

    bumped = []
    for key, window, limit in (
        (ip_key, OTP_SEND_IP_WINDOW_SECONDS, OTP_SEND_IP_MAX),
        (phone_counter_key, OTP_SEND_PHONE_WINDOW_SECONDS, OTP_SEND_PHONE_MAX),
        (daily_key, 24 * 60 * 60, daily_max),
    ):
        count = _bump(key, window)
        bumped.append(key)
        if count > limit:
            for k in bumped:  # bu isteğin artırdıklarını geri al
                _unbump(k)
            cache.delete(cooldown_key)  # gönderim olmadı, bekleme de gerekmez
            return "limit"
    return None


def otp_send_allowed(request, phone_key):
    """True ise gönderime izin var (ve sayaç artırıldı)."""
    return otp_send_check(request, phone_key) is None


def _unbump(key):
    try:
        cache.decr(key)
    except ValueError:  # anahtar yok / süresi dolmuş
        pass


def rollback_otp_send(request, phone_key, code_request_counted=True):
    """
    Kod GÖNDERİLEMEDİYSE (WhatsApp/Meta hatası) harcanan hakları iade et.
    Aksi halde sağlayıcı hata verdiği sürece müşteri hiçbir şey almadan
    saatlik numara/IP limitine takılıyordu (5 başarısız denemeden sonra
    1 saat kilit).
    """
    cache.delete(f"otp_cooldown:{phone_key}")
    _unbump(f"otp_ip:{_client_ip(request)}")
    _unbump(f"otp_phone:{phone_key}")
    _unbump("otp_global_daily")
    if code_request_counted:  # only the login flow calls register_code_request()
        _unbump(_code_request_key(request, phone_key))


def release_otp_cooldown(phone_key):
    """Geriye dönük uyumluluk: yalnızca bekleme süresini kaldırır."""
    cache.delete(f"otp_cooldown:{phone_key}")