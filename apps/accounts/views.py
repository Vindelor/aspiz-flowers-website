
import secrets
import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.orders.models import Order

from . import sms
from django.utils import timezone

from .forms import (
    LoginRequestForm,
    LoginVerifyForm,
    ProfileForm,
    RegisterForm,
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
_ACCOUNT_NOT_FOUND_MESSAGE = "Bu telefon numarasıyla kayıtlı bir hesap bulunamadı."
_CODE_SEND_FAILED_MESSAGE = "Giriş kodu gönderilemedi. Lütfen daha sonra tekrar deneyin."


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
    LoginCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
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
    return login_code


def login_request_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = LoginRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone_candidates = phone_lookup_candidates(form.cleaned_data["phone"])
        # Any one representation is fine as the rate-limit/lockout key —
        # they all refer to the same number, and the key just needs to be
        # stable across requests for the same phone.
        lookup_key = next(iter(phone_candidates))

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
            return _auth_error(request, {"__all__": [_ACCOUNT_NOT_FOUND_MESSAGE]}, 400)

        clear_login_failures(request, lookup_key)
        register_code_request(request, lookup_key)

        try:
            login_code = _issue_login_code(user)
        except Exception:
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

        # Flips a just-registered (inactive) account to active the moment
        # its verification code checks out. No-op for the normal login
        # flow, where the user is already active.
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

    clear_code_verify_failures(request, user_id)
    request.session.pop("login_code_id", None)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
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
            phone = form.cleaned_data["phone"]
            # A previous registration with this phone may exist but never
            # got verified (RegisterForm.clean_phone only blocks *active*
            # accounts, so it let this one through). Clear it out first —
            # otherwise the DB-level unique constraint on phone would raise
            # an IntegrityError on save, and the person who mistyped/never
            # got their first code would be permanently locked out of that
            # number.
            User.objects.filter(phone=phone, is_active=False).delete()

            user = form.save(commit=False)
            # Held inactive — and NOT logged in — until the SMS code is
            # verified below, so nobody can enter the site on a phone
            # number they don't actually control. login_verify_view flips
            # this to True and calls login() once the code checks out.
            user.is_active = False
            user.save()

            try:
                login_code = _issue_login_code(user)
            except Exception:
                # Nobody could receive the code, so don't leave a dangling
                # unverifiable account sitting on this phone number.
                user.delete()
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