import logging
import re

import phonenumbers
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SmsSendError(Exception):
    """Raised when the WhatsApp OTP could not be sent."""


def _to_whatsapp_number(raw_phone):
    """'05551234567' یا '905551234567' -> '905551234567' (بدون +)."""
    try:
        parsed = phonenumbers.parse(str(raw_phone).strip(), "TR")
        if phonenumbers.is_valid_number(parsed):
            return re.sub(r"\D", "", phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
    except phonenumbers.NumberParseException:
        pass
    return None



def _is_real_value(value):
    """False for empty values and for the env.example placeholders ('your-...')."""
    value = (value or "").strip()
    return bool(value) and not value.lower().startswith("your-")


def send_otp_sms(phone, code):
    if not (
        _is_real_value(settings.WHATSAPP_PHONE_NUMBER_ID)
        and _is_real_value(settings.WHATSAPP_ACCESS_TOKEN)
    ):
        logger.error(
            "WhatsApp OTP not sent: WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN "
            "are empty or still placeholders in .env."
        )

        raise SmsSendError("WhatsApp ayarları (.env) yapılandırılmamış.")

    to = _to_whatsapp_number(phone)
    if not to:
        raise SmsSendError("Geçersiz telefon numarası.")

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_OTP_TEMPLATE_NAME,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": code}]},
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": code}],
                },
            ],
        },
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        # Meta hatanın nedenini (geçersiz token, onaysız şablon, dil uyuşmazlığı...)
        # cevabın gövdesinde döner; sadece "401 Client Error" yazmak teşhisi imkânsız kılıyor.
        body = getattr(getattr(exc, "response", None), "text", "") or ""
        logger.error("WhatsApp OTP request failed: %s | Meta response: %s", exc, body[:500])
        raise SmsSendError("WhatsApp mesajı gönderilemedi.") from exc
    return True