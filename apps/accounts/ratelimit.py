"""
Lightweight cache-based rate limiting for the login and register endpoints.

Uses Django's default cache (LocMemCache, no extra config needed) instead of
adding a dependency like django-axes. Good enough for a single-process
deployment; if the app later runs behind multiple gunicorn/uwsgi workers,
point CACHES at Redis/Memcached in settings.py so the counters are shared
across processes — LocMemCache state is per-process and won't work correctly
otherwise.
"""
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
CODE_VERIFY_MAX_ATTEMPTS = 5
CODE_VERIFY_LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
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
    return f"code_verify_lock:{_client_ip(request)}:{user_id}"


def is_code_verify_locked(request, user_id):
    return cache.get(_code_verify_key(request, user_id), 0) >= CODE_VERIFY_MAX_ATTEMPTS


def register_code_verify_failure(request, user_id):
    key = _code_verify_key(request, user_id)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, CODE_VERIFY_LOCKOUT_SECONDS)
    return attempts


def clear_code_verify_failures(request, user_id):
    cache.delete(_code_verify_key(request, user_id))


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


def otp_send_allowed(request, phone_key):
    """True ise gönderime izin var (ve sayaç artırıldı)."""
    if not cache.add(f"otp_cooldown:{phone_key}", 1, OTP_RESEND_COOLDOWN_SECONDS):
        return False
    ip_count = _bump(f"otp_ip:{_client_ip(request)}", OTP_SEND_IP_WINDOW_SECONDS)
    phone_count = _bump(f"otp_phone:{phone_key}", OTP_SEND_PHONE_WINDOW_SECONDS)
    return ip_count <= OTP_SEND_IP_MAX and phone_count <= OTP_SEND_PHONE_MAX


def release_otp_cooldown(phone_key):
    """Gönderim başarısız olduysa kullanıcı 60 sn boşuna beklemesin."""
    cache.delete(f"otp_cooldown:{phone_key}")
