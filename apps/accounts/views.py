import logging
import secrets
import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.cart.cart import merge_guest_cart
from apps.orders.models import Order

from . import sms
from django.utils import timezone

from .forms import (
    LoginRequestForm,
    LoginVerifyForm,
    ProfileForm,
    RegisterForm,
    canonical_phone_key,
    phone_lookup_candidates,
    stale_unverified_users,
)
from .models import LoginCode
from .ratelimit import (
    clear_code_verify_failures,
    clear_login_failures,
    is_code_request_rate_limited,
    is_code_verify_locked,
    is_login_locked,
    is_register_rate_limited,
    otp_send_check,
    register_attempt,
    rollback_otp_send,
    register_code_request,
    register_code_verify_failure,
    register_login_failure,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


LOGIN_LOCKOUT_MESSAGE = "Çok fazla başarısız giriş denemesi yapıldı. Lütfen 15 dakika sonra tekrar deneyin."
REGISTER_RATE_LIMIT_MESSAGE = "Çok fazla kayıt denemesi yapıldı. Lütfen daha sonra tekrar deneyin."
CODE_REQUEST_RATE_LIMIT_MESSAGE = "Çok fazla kod talebi yapıldı. Lütfen biraz sonra tekrar deneyin."
CODE_VERIFY_LOCKOUT_MESSAGE = "Çok fazla hatalı kod denemesi yapıldı. Lütfen 15 dakika sonra tekrar deneyin."
OTP_COOLDOWN_MESSAGE = "Yeni kod için lütfen 60 saniye bekleyin."
_PENDING_REGISTRATION_MESSAGE = (
    "Kaydınız henüz doğrulanmamış. Lütfen \"Kayıt Ol\" sekmesinden aynı numarayla tekrar kayıt olup kodu girin."
)
_ACCOUNT_NOT_FOUND_MESSAGE = "Bu telefon numarasıyla kayıtlı bir hesap bulunamadı."
_CODE_SEND_FAILED_MESSAGE = "Giriş kodu gönderilemedi. Lütfen daha sonra tekrar deneyin."


def _safe_next(request, value):
    """`next` kullanıcıdan geliyor: yalnızca bu siteye ait adreslere izin ver (open redirect önlemi)."""
    value = value or ""
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return ""


def _remember_next(request):
    """
    @login_required, kullanıcıyı /accounts/login/?next=/orders/checkout/ adresine
    gönderiyor; ama kod doğrulama ayrı bir istek olduğu için `next` kayboluyor ve
    giriş sonrası kullanıcı hep ana sayfaya düşüyordu. Oturumda saklıyoruz.
    """
    nxt = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    if nxt:
        request.session["login_next"] = nxt
    else:
        request.session.pop("login_next", None)


def _issue_login_code(user):
    """
    Create a fresh LoginCode for `user`, text it via SMS, and return it.

    Shared by login_request_view (existing account, passwordless login) and
    register_view (brand-new account, one-time phone verification) so both
    flows send/verify codes exactly the same way. Any previously pending
    code for this user is invalidated first. If the SMS fails to send, the
    LoginCode row is rolled back and the exception re-raised so the caller
    can show an error instead of stranding a code nobody received.
    """
    code = f"{secrets.randbelow(1000000):06d}"
    login_code = LoginCode.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    try:
        sms.send_otp_sms(user.phone, code)
    except Exception:
        login_code.delete()
        raise
    # Only now (send succeeded) retire the previous pending codes.
    LoginCode.objects.filter(user=user, used_at__isnull=True).exclude(pk=login_code.pk).update(used_at=timezone.now())
    return login_code


def login_request_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = LoginRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _remember_next(request)
        phone_candidates = phone_lookup_candidates(form.cleaned_data["phone"])
        # Any one representation is fine as the rate-limit/lockout key —
        # they all refer to the same number, and the key just needs to be
        # stable across requests for the same phone.
        # Kararlı (E.164) anahtar: set'ten rastgele eleman almak aynı numara için
        # farklı sayaçlar üretip limiti aşmaya izin veriyordu.
        lookup_key = canonical_phone_key(form.cleaned_data["phone"])

        # Locked/limited by phone — this is the only identifier in the
        # login flow now, so it doubles as the secret being guessed.
        if is_login_locked(request, lookup_key):
            return _auth_error(request, {"__all__": [LOGIN_LOCKOUT_MESSAGE]}, 429)

        # Also cap how many codes we'll send to a given number in a row,
        # so an attacker can't dodge the 5-guess cap below by simply
        # requesting a fresh code every few tries.
        if is_code_request_rate_limited(request, lookup_key):
            return _auth_error(request, {"__all__": [CODE_REQUEST_RATE_LIMIT_MESSAGE]}, 429)

        user = User.objects.filter(phone__in=phone_candidates, is_active=True).first()
        if not user:
            register_login_failure(request, lookup_key)
            # Kayıt olmuş ama kodu hiç girmemiş kişi: "hesap yok" demek yerine
            # nasıl devam edeceğini söyle.
            if stale_unverified_users(lookup_key).exists():
                return _auth_error(request, {"__all__": [_PENDING_REGISTRATION_MESSAGE]}, 400)
            return _auth_error(request, {"__all__": [_ACCOUNT_NOT_FOUND_MESSAGE]}, 400)

        # ===== FIX =====
        # Admin/staff hesapları yalnızca OTP ile giriş yapamaz; yönetim paneli
        # şifre istemeli. Bu hesaplar müşteri giriş formunda "yok" gibi davranır.
        if user.is_staff or user.is_superuser:
            register_login_failure(request, lookup_key)
            return _auth_error(request, {"__all__": [_ACCOUNT_NOT_FOUND_MESSAGE]}, 400)
        # ===== /FIX =====

        clear_login_failures(request, lookup_key)

        # Hesap hatalı kod denemelerinden dolayı kilitliyse yeni kod GÖNDERME:
        # kod ücretli, üstelik doğru kod bile kilit bitene kadar reddediliyor.
        if is_code_verify_locked(request, user.pk):
            return _auth_error(request, {"__all__": [CODE_VERIFY_LOCKOUT_MESSAGE]}, 429)

        # Para harcayan işlem: IP başına / numara başına / 60 sn bekleme limiti.
        blocked = otp_send_check(request, lookup_key)
        if blocked:
            message = OTP_COOLDOWN_MESSAGE if blocked == "cooldown" else CODE_REQUEST_RATE_LIMIT_MESSAGE
            return _auth_error(request, {"__all__": [message]}, 429)
        register_code_request(request, lookup_key)

        try:
            login_code = _issue_login_code(user)
        except Exception:
            logger.exception("Login code could not be sent")
            rollback_otp_send(request, lookup_key)
            return _auth_error(request, {"__all__": [_CODE_SEND_FAILED_MESSAGE]}, 503)
        request.session["login_code_id"] = login_code.pk
        if _is_ajax(request):
            return JsonResponse({"success": True, "step": "verify", "message": "Giriş kodu telefonunuza gönderildi."})
        return redirect("accounts:login_verify_page")
    return _auth_form_response(request, form)


def login_verify_page(request):
    if not request.session.get("login_code_id"):
        return redirect("accounts:login")
    return render(request, "accounts/login.html", {"otp_sent": True})


def login_verify_view(request):
    form = LoginVerifyForm(request.POST or None)
    code_id = request.session.get("login_code_id")
    if request.method != "POST" or not form.is_valid() or not code_id:
        return _auth_error(request, {"code": ["Giriş kodu geçersiz veya süresi doldu."]}, 400)

    with transaction.atomic():
        login_code = (
            LoginCode.objects.select_for_update()
            .select_related("user")
            .filter(pk=code_id)
            .first()
        )
        # Note: unlike before, we don't require login_code.user.is_active
        # here — a brand-new registration is deliberately created inactive
        # (see register_view) and only activated a few lines down, once its
        # code is confirmed. Login-flow codes are always for already-active
        # users, so this check never mattered for that path anyway.
        if not login_code:
            request.session.pop("login_code_id", None)
            return _auth_error(request, {"code": ["Giriş kodu geçersiz veya süresi doldu."]}, 400)

        user_id = login_code.user_id

        # Locked independently of which code is currently pending: asking
        # for a brand-new code does NOT reset this counter, unlike the
        # per-row `attempts` field on LoginCode.
        if is_code_verify_locked(request, user_id):
            request.session.pop("login_code_id", None)
            return _auth_error(request, {"__all__": [CODE_VERIFY_LOCKOUT_MESSAGE]}, 429)

        if not login_code.is_valid:
            return _auth_error(request, {"code": ["Giriş kodu geçersiz veya süresi doldu."]}, 400)

        login_code.attempts += 1
        login_code.save(update_fields=["attempts"])
        if not check_password(form.cleaned_data["code"], login_code.code_hash):
            register_code_verify_failure(request, user_id)
            return _auth_error(request, {"code": ["Giriş kodu hatalı."]}, 400)

        login_code.used_at = timezone.now()
        login_code.save(update_fields=["used_at"])
        user = login_code.user

        # ===== FIX =====
        # Savunma ikinci katman: login_request_view'dan sonra bir hesap staff
        # yapılmış olsa bile OTP ile oturum açılmasın.
        if user.is_staff or user.is_superuser:
            return _auth_error(request, {"code": ["Giriş kodu geçersiz veya süresi doldu."]}, 400)
        # ===== /FIX =====

        # Flips a just-registered (inactive) account to active the moment
        # its verification code checks out. No-op for the normal login
        # flow, where the user is already active.
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

    clear_code_verify_failures(request, user_id)
    request.session.pop("login_code_id", None)
    stored_next = request.session.pop("login_next", "")
    guest_session_key = request.session.session_key  # login() rotates it
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    merge_guest_cart(user, guest_session_key)

    next_url = _safe_next(request, request.POST.get("next")) or _safe_next(request, stored_next)
    return _auth_success(request, {"redirect_url": next_url or reverse("core:home")})


def _auth_success(request, data):
    return JsonResponse({"success": True, **data}) if _is_ajax(request) else redirect(data.get("redirect_url", "accounts:login"))


def _auth_error(request, errors, status=400):
    if _is_ajax(request):
        return JsonResponse({"success": False, "errors": errors}, status=status)
    messages.error(request, next(iter(errors.values()))[0])
    return redirect("accounts:login")


def _auth_form_response(request, form):
    if _is_ajax(request):
        return JsonResponse({"success": False, "errors": form.errors}, status=400)
    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": _safe_next(request, request.POST.get("next") or request.GET.get("next"))},
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    next_url = request.POST.get("next") or request.GET.get("next") or ""
    ajax = _is_ajax(request)

    if request.method == "POST":
        # Guard against scripted mass account creation from a single IP.
        if is_register_rate_limited(request):
            if ajax:
                return JsonResponse(
                    {"success": False, "errors": {"__all__": [REGISTER_RATE_LIMIT_MESSAGE]}},
                    status=429,
                )
            messages.error(request, REGISTER_RATE_LIMIT_MESSAGE)
            return render(request, "accounts/register.html", {"form": RegisterForm(), "next": next_url})

        form = RegisterForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            _remember_next(request)

            # Para harcayan işlem: kullanıcı oluşturmadan ÖNCE limiti kontrol et.
            blocked = otp_send_check(request, phone)
            if blocked:
                message = OTP_COOLDOWN_MESSAGE if blocked == "cooldown" else CODE_REQUEST_RATE_LIMIT_MESSAGE
                if ajax:
                    return JsonResponse({"success": False, "errors": {"__all__": [message]}}, status=429)
                messages.error(request, message)
                return render(request, "accounts/register.html", {"form": RegisterForm(), "next": next_url})

            # A previous registration with this phone may exist but never
            # got verified (RegisterForm.clean_phone only blocks *active*
            # accounts, so it let this one through). Clear it out first —
            # otherwise the DB-level unique constraint on phone would raise
            # an IntegrityError on save, and the person who mistyped/never
            # got their first code would be permanently locked out of that
            # number.
            # Yalnızca doğrulanmamış eski kayıtlar silinir; yönetici tarafından
            # kapatılmış / siparişi olan hesaplar silinmez (clean_phone zaten
            # bunlar için kayıt açılmasını engelliyor).
            stale_unverified_users(phone).delete()

            user = form.save(commit=False)
            # Held inactive — and NOT logged in — until the SMS code is
            # verified below, so nobody can enter the site on a phone
            # number they don't actually control. login_verify_view flips
            # this to True and calls login() once the code checks out.
            user.is_active = False
            try:
                with transaction.atomic():
                    user.save()
            except IntegrityError:
                # Aynı numarayla eşzamanlı iki kayıt (çift tıklama / iki sekme):
                # DB unique kısıtı 500 hatası yerine anlaşılır bir mesaja dönsün.
                rollback_otp_send(request, phone, code_request_counted=False)
                duplicate_message = "Bu telefon numarası zaten kayıtlı."
                if ajax:
                    return JsonResponse({"success": False, "errors": {"phone": [duplicate_message]}}, status=400)
                messages.error(request, duplicate_message)
                return render(request, "accounts/register.html", {"form": RegisterForm(), "next": next_url})

            try:
                login_code = _issue_login_code(user)
            except Exception:
                logger.exception("Registration code could not be sent")
                # Nobody could receive the code, so don't leave a dangling
                # unverifiable account sitting on this phone number.
                user.delete()
                rollback_otp_send(request, phone, code_request_counted=False)
                if ajax:
                    return JsonResponse({"success": False, "errors": {"__all__": [_CODE_SEND_FAILED_MESSAGE]}}, status=503)
                messages.error(request, _CODE_SEND_FAILED_MESSAGE)
                return render(request, "accounts/register.html", {"form": RegisterForm(), "next": next_url})

            request.session["login_code_id"] = login_code.pk
            if ajax:
                return JsonResponse(
                    {"success": True, "step": "verify", "message": "Hesabınızı doğrulamak için telefonunuza bir kod gönderdik."}
                )
            messages.info(request, "Hesabınızı doğrulamak için telefonunuza bir kod gönderdik.")
            return redirect("accounts:login_verify_page")

        register_attempt(request)
        if ajax:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Çıkış yapıldı.")
    return redirect("core:home")


@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil güncellendi.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    orders = request.user.orders.order_by("-created_at")[:10]
    return render(request, "accounts/profile.html", {"form": form, "orders": orders})