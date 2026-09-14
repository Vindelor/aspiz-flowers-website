
import secrets
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from requests import RequestException

from apps.orders.models import Order

from . import google_oauth
from django.utils import timezone

from .forms import (
    LoginRequestForm,
    LoginVerifyForm,
    ProfileForm,
    RegisterForm,
    _unique_username_from_email,
    phone_lookup_candidates,
)
from .models import LoginCode
from .ratelimit import (
    clear_code_verify_failures,
    clear_login_failures,
    is_code_request_rate_limited,
    is_code_verify_locked,
    is_login_locked,
    is_register_rate_limited,
    register_attempt,
    register_code_request,
    register_code_verify_failure,
    register_login_failure,
)

User = get_user_model()


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


LOGIN_LOCKOUT_MESSAGE = "Çok fazla başarısız giriş denemesi yapıldı. Lütfen 15 dakika sonra tekrar deneyin."
REGISTER_RATE_LIMIT_MESSAGE = "Çok fazla kayıt denemesi yapıldı. Lütfen daha sonra tekrar deneyin."
CODE_REQUEST_RATE_LIMIT_MESSAGE = "Çok fazla kod talebi yapıldı. Lütfen biraz sonra tekrar deneyin."
CODE_VERIFY_LOCKOUT_MESSAGE = "Çok fazla hatalı kod denemesi yapıldı. Lütfen yeniden giriş yapmayı deneyin."
_ACCOUNT_NOT_FOUND_MESSAGE = "E-posta ve telefon numarası eşleşmedi."
_CODE_SEND_FAILED_MESSAGE = "Giriş kodu gönderilemedi. E-posta ayarlarını kontrol edin."


def _issue_login_code(user):
    """
    Create a fresh LoginCode for `user`, email it, and return it.

    Shared by login_request_view (existing account, passwordless login) and
    register_view (brand-new account, one-time email verification) so both
    flows send/verify codes exactly the same way. Any previously pending
    code for this user is invalidated first. If the email fails to send,
    the LoginCode row is rolled back and the exception re-raised so the
    caller can show an error instead of stranding a code nobody received.
    """
    code = f"{secrets.randbelow(1000000):06d}"
    LoginCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    login_code = LoginCode.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    try:
        send_mail(
            subject="Aspiz Flowers giriş kodunuz",
            message=f"Giriş kodunuz: {code}\nBu kod 10 dakika geçerlidir ve tek kullanımlıktır.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        login_code.delete()
        raise
    return login_code


def login_request_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = LoginRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        phone_candidates = phone_lookup_candidates(form.cleaned_data["phone"])

        # Locked/limited by email ONLY (never by email+phone together) —
        # the phone number is exactly the secret being guessed here, so a
        # key that includes it would let an attacker try a different phone
        # every single time and never trip the counter.
        if is_login_locked(request, email):
            return _auth_error(request, {"__all__": [LOGIN_LOCKOUT_MESSAGE]}, 429)

        # Also cap how many codes we'll send to a given address in a row,
        # so a correct-but-not-yours email+phone pair can't be used to
        # spam someone's inbox, and so an attacker can't dodge the 5-guess
        # cap below by simply requesting a fresh code every few tries.
        if is_code_request_rate_limited(request, email):
            return _auth_error(request, {"__all__": [CODE_REQUEST_RATE_LIMIT_MESSAGE]}, 429)

        user = User.objects.filter(email__iexact=email, phone__in=phone_candidates, is_active=True).first()
        if not user:
            register_login_failure(request, email)
            return _auth_error(request, {"__all__": [_ACCOUNT_NOT_FOUND_MESSAGE]}, 400)

        clear_login_failures(request, email)
        register_code_request(request, email)

        try:
            login_code = _issue_login_code(user)
        except Exception:
            return _auth_error(request, {"__all__": [_CODE_SEND_FAILED_MESSAGE]}, 503)
        request.session["login_code_id"] = login_code.pk
        if _is_ajax(request):
            return JsonResponse({"success": True, "step": "verify", "message": "Giriş kodu e-posta adresinize gönderildi."})
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

        # Flips a just-registered (inactive) account to active the moment
        # its verification code checks out. No-op for the normal login
        # flow, where the user is already active.
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

    clear_code_verify_failures(request, user_id)
    request.session.pop("login_code_id", None)
    login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
    return _auth_success(request, {"redirect_url": request.POST.get("next") or reverse("core:home")})


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
    return render(request, "accounts/login.html", {"form": form})


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
            email = form.cleaned_data["email"]
            # A previous registration with this email may exist but never
            # got verified (RegisterForm.clean_email only blocks *active*
            # accounts, so it let this one through). Clear it out first —
            # otherwise the DB-level unique constraint on email would raise
            # an IntegrityError on save, and the person who mistyped/never
            # got their first code would be permanently locked out of that
            # address.
            User.objects.filter(email__iexact=email, is_active=False).delete()

            user = form.save(commit=False)
            # Held inactive — and NOT logged in — until the email code is
            # verified below, so nobody can enter the site on an email
            # address they don't actually control. login_verify_view flips
            # this to True and calls login() once the code checks out.
            user.is_active = False
            user.save()

            try:
                login_code = _issue_login_code(user)
            except Exception:
                # Nobody could receive the code, so don't leave a dangling
                # unverifiable account sitting on this email/phone.
                user.delete()
                if ajax:
                    return JsonResponse({"success": False, "errors": {"__all__": [_CODE_SEND_FAILED_MESSAGE]}}, status=503)
                messages.error(request, _CODE_SEND_FAILED_MESSAGE)
                return render(request, "accounts/register.html", {"form": RegisterForm(), "next": next_url})

            request.session["login_code_id"] = login_code.pk
            if ajax:
                return JsonResponse(
                    {"success": True, "step": "verify", "message": "Hesabınızı doğrulamak için e-posta adresinize bir kod gönderdik."}
                )
            messages.info(request, "Hesabınızı doğrulamak için e-posta adresinize bir kod gönderdik.")
            return redirect("accounts:login_verify_page")

        register_attempt(request)
        if ajax:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form, "next": next_url})


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


def google_login(request):
    """Redirects to Google's consent screen. Hidden in templates via
    google_oauth_enabled until GOOGLE_OAUTH_CLIENT_ID/SECRET are set."""
    if not settings.GOOGLE_OAUTH_ENABLED:
        messages.error(request, "Google ile giriş şu anda kullanılamıyor.")
        return redirect("accounts:login")

    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    next_url = request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        request.session["google_oauth_next"] = next_url
    return redirect(google_oauth.build_authorization_url(state))


def google_callback(request):
    """
    Handles Google's redirect back after consent. Matches the account by
    email: links to an existing account if one already has that email
    (e.g. someone who first registered normally), otherwise creates a new
    account. Accounts created this way get an unusable password (see
    set_unusable_password) since they only ever log in via Google — the
    "şifremi unuttum" flow correctly won't apply to them.
    """
    if not settings.GOOGLE_OAUTH_ENABLED:
        messages.error(request, "Google ile giriş şu anda kullanılamıyor.")
        return redirect("accounts:login")

    error = request.GET.get("error")
    if error:
        messages.error(request, "Google girişi iptal edildi.")
        return redirect("accounts:login")

    state = request.GET.get("state")
    expected_state = request.session.pop("google_oauth_state", None)
    if not state or not expected_state or state != expected_state:
        messages.error(request, "Google girişi doğrulanamadı, lütfen tekrar deneyin.")
        return redirect("accounts:login")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Google girişi doğrulanamadı, lütfen tekrar deneyin.")
        return redirect("accounts:login")

    try:
        access_token = google_oauth.exchange_code_for_token(code)
        userinfo = google_oauth.fetch_userinfo(access_token)
    except RequestException:
        messages.error(request, "Google ile bağlantı kurulamadı, lütfen tekrar deneyin.")
        return redirect("accounts:login")

    email = userinfo.get("email")
    if not email or not userinfo.get("email_verified"):
        messages.error(request, "Google hesabınızın e-postası doğrulanmamış.")
        return redirect("accounts:login")

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User(
            username=_unique_username_from_email(email),
            email=email,
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
        )
        user.set_unusable_password()
        user.save()
    elif not user.is_active:
        # An inactive row here is an abandoned manual registration that
        # never verified its email code (see register_view). Google has
        # just verified that same address on our behalf, so activate it
        # rather than leaving a stale is_active=False despite a real login.
        user.is_active = True
        user.save(update_fields=["is_active"])

    login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
    messages.success(request, "Google hesabınızla giriş yaptınız.")

    next_url = request.session.pop("google_oauth_next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("core:home")