"""
Sends one-time login/verification codes via SMS using the Netgsm REST v2 API
(chosen for Turkish numbers — cheaper and faster delivery than international
providers, and no sender-ID restrictions to fight with).

One-time setup (do this in your Netgsm panel before this works):
1. netgsm.com.tr -> hesabınıza giriş yapın -> Ayarlar -> API İşlemleri:
   enable REST API access for your account (and add your server's IP if
   Netgsm asks for an allow-list).
2. Get/approve an SMS header (başlık) — the sender name recipients see
   instead of a phone number. This can take a day or two to approve.
3. Put NETGSM_USERCODE, NETGSM_PASSWORD, NETGSM_HEADER in your .env — see
   .env.example.

Unlike apps/orders/whatsapp.py (a best-effort "new order" notification that
fails silently so checkout never breaks), a failed OTP send has nowhere to
hide: apps/accounts/views.py relies on send_otp_sms raising on any failure,
so the pending LoginCode row gets rolled back and the person sees a real
error instead of waiting forever for a code that was never sent.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SEND_ENDPOINT = "https://api.netgsm.com.tr/sms/rest/v2/send"

# Netgsm's own result code for /sms/rest/v2/send — "00" is the only success
# code, anything else (bad credentials, header not approved yet, malformed
# number, etc.) is a rejection.
_SUCCESS_CODE = "00"


class SmsSendError(Exception):
    """Raised when Netgsm rejects the SMS, or the request itself fails."""


def send_otp_sms(phone_digits, code):
    """
    Sends `code` to `phone_digits` (E.164 digits with no leading '+', e.g.
    "905551234567" — the same shape phone numbers are stored in; see
    apps/accounts/forms.py). Raises SmsSendError on any failure.
    """
    if not (settings.NETGSM_USERCODE and settings.NETGSM_PASSWORD and settings.NETGSM_HEADER):
        logger.error("SMS OTP not sent: Netgsm settings are not configured (.env).")
        raise SmsSendError("Netgsm ayarları (.env) henüz yapılandırılmamış.")

    payload = {
        "msgheader": settings.NETGSM_HEADER,
        "encoding": "TR",
        # Transactional/security code, not a commercial message — "0" skips
        # the İYS commercial-messaging filter, which doesn't apply here.
        "iysfilter": "0",
        "messages": [
            {"msg": f"Aspiz Flowers giris kodunuz: {code}", "no": phone_digits},
        ],
    }

    try:
        response = requests.post(
            SEND_ENDPOINT,
            json=payload,
            auth=(settings.NETGSM_USERCODE, settings.NETGSM_PASSWORD),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("Netgsm SMS request failed: %s", exc)
        raise SmsSendError("SMS gönderilemedi (bağlantı hatası).") from exc
    except ValueError as exc:
        logger.error("Netgsm SMS returned a non-JSON response.")
        raise SmsSendError("SMS gönderilemedi (beklenmeyen yanıt).") from exc

    if str(data.get("code")) != _SUCCESS_CODE:
        logger.error("Netgsm SMS rejected: %s", data)
        raise SmsSendError(f"SMS gönderilemedi (Netgsm kodu: {data.get('code')}).")

    return True
