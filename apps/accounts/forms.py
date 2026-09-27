import re

import phonenumbers
from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm

from .models import User

# Only Turkish numbers are accepted, typed either as "0555 123 45 67" or
# with the country code ("+90 555 123 45 67") — this is also the region
# used to parse a number typed without a leading "+".
DEFAULT_PHONE_REGION = "TR"


def _clean_phone_number(raw_phone):
    """
    Validates that `raw_phone` is a real, dialable Turkish phone number
    using Google's libphonenumber, instead of the old "10+ digits" check —
    which let anyone through arbitrary digit strings like "1111111111".
    Any number that doesn't belong to Turkey (region "TR") is rejected,
    regardless of which country code the user typed. Returns the number as
    digits only (E.164 minus the "+"), which is the same shape phone
    numbers are stored/matched in elsewhere (see login_request_view's phone
    lookup).
    """
    error = forms.ValidationError("Geçerli bir Türkiye telefon numarası girin (05XX XXX XX XX veya +90 5XX XXX XX XX).")
    try:
        parsed = phonenumbers.parse(raw_phone.strip(), DEFAULT_PHONE_REGION)
    except phonenumbers.NumberParseException:
        raise error
    if not phonenumbers.is_valid_number(parsed) or phonenumbers.region_code_for_number(parsed) != "TR":
        raise error
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return re.sub(r"\D", "", e164)


def phone_lookup_candidates(raw_phone):
    """
    Login (LoginRequestForm) needs to find an existing user by phone, but
    phones stored *before* this validation change are plain digit-strings
    typed by the user (e.g. a Turkish "0555 123 45 67" saved as
    "05551234567"), while phones stored *after* this change are
    libphonenumber-normalized (E.164 digits, e.g. "905551234567" — no
    leading 0). Returns every representation of `raw_phone` worth trying
    against the `phone` column, so both old and new accounts keep matching
    regardless of exactly how the number was typed at login vs. signup.
    """
    candidates = set()
    raw_digits = re.sub(r"\D", "", raw_phone)
    if raw_digits:
        candidates.add(raw_digits)
    try:
        parsed = phonenumbers.parse(raw_phone.strip(), DEFAULT_PHONE_REGION)
        if phonenumbers.is_valid_number(parsed):
            e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            candidates.add(re.sub(r"\D", "", e164))
    except phonenumbers.NumberParseException:
        pass
    return candidates


def _unique_username_from_phone(phone_digits):
    """905551234567 -> 'uye5551234567', then uye5551234567-2, -3... if taken.
    Drops the leading country-code digits so the username isn't simply the
    phone number restated in full."""
    base = f"uye{phone_digits[-10:]}"
    username = base
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


class RegisterForm(forms.ModelForm):
    full_name = forms.CharField(
        label="Ad Soyad",
        max_length=150,
        required=True,
    )
    phone = forms.CharField(label="Telefon Numarası", max_length=20, required=True)
    terms = forms.BooleanField(
        label="Kullanım Şartları'nı okudum ve kabul ediyorum.",
        required=True,
        error_messages={"required": "Devam etmek için kullanım şartlarını kabul etmelisiniz."},
    )

    class Meta:
        model = User
        fields = ("full_name", "phone", "terms")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("autocomplete", "off")

    def clean_phone(self):
        phone = _clean_phone_number(self.cleaned_data["phone"])
        # is_active=True only: an inactive row is a previous registration
        # that never verified its SMS code (see register_view), and
        # doesn't deserve to permanently squat on the number.
        if User.objects.filter(phone=phone, is_active=True).exists():
            raise forms.ValidationError("Bu telefon numarası zaten kayıtlı.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = _unique_username_from_phone(self.cleaned_data["phone"])
        user.phone = self.cleaned_data["phone"]
        user.set_unusable_password()

        full_name = self.cleaned_data["full_name"].strip()
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""

        if commit:
            user.save()
        return user


class LoginRequestForm(forms.Form):
    phone = forms.CharField(label="Telefon Numarası", max_length=20)


class LoginVerifyForm(forms.Form):
    code = forms.RegexField(label="Giriş Kodu", regex=r"^\d{6}$", max_length=6, min_length=6)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "address")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bu form giriş modalıyla aynı görsel dili kullanıyor (bkz.
        # templates/accounts/profile.html + site.css bölüm 7/10: .form-group,
        # .input-with-icon). Buradaki class'lar Tailwind değil, o CSS
        # sınıflarıyla eşleşiyor; bilerek INPUT_CLASS kullanmıyoruz.
        for name, field in self.fields.items():
            if name == "address":
                field.widget.attrs.setdefault("rows", 3)
            field.widget.attrs.setdefault("autocomplete", "off")

    def clean_phone(self):
        phone = _clean_phone_number(self.cleaned_data["phone"])
        exists = User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists()
        if exists:
            raise forms.ValidationError("Bu telefon numarası zaten kullanılıyor.")
        return phone


class StyledPasswordResetForm(PasswordResetForm):
    """Uses the same .form-group/.input-with-icon design as ProfileForm/the login modal."""


class StyledSetPasswordForm(SetPasswordForm):
    """Uses the same .form-group/.input-with-icon design as ProfileForm/the login modal."""