
from pathlib import Path
import os
import sys
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, "apps"))

load_dotenv(BASE_DIR / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# DEBUG defaults to False now (fail-safe): a missing/broken .env on a real
# server must never silently turn debug mode on. Local dev sets DEBUG=True
# explicitly in .env instead.
DEBUG = os.getenv("DEBUG", "False") == "True"

# SECRET_KEY has no insecure fallback anymore. In DEBUG mode we still allow
# a fixed dev-only value so `runserver` works out of the box; in production
# (DEBUG=False) a missing SECRET_KEY now hard-crashes startup instead of
# silently running with a publicly-known key.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY ortam değişkeni tanımlı değil. .env dosyasını kontrol edin "
            "— production'da gerçek bir SECRET_KEY olmadan uygulama başlatılamaz."
        )

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Admin panel path is configurable so it doesn't sit on the well-known
# "/admin/" URL that every scanner/bot probes by default. Set ADMIN_URL in
# .env for production (must end with "/"), e.g. ADMIN_URL=y-panel-x9k2/
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # local apps
    "accounts",
    "products",
    "cart",
    "orders",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files directly from the app process — no
    # Nginx "static location" config needed. Must sit right after
    # SecurityMiddleware and before everything else (whitenoise docs).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "config.middleware.AdminLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.cart.context_processors.cart",
                "apps.core.context_processors.nav_categories",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "shop_db"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        # utf8mb4 is required for Turkish/Persian characters and emoji (badges,
        # admin status icons) to store correctly — MySQL's plain "utf8" is a
        # legacy 3-byte-only charset and will silently mangle some characters.
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

AUTH_USER_MODEL = "accounts.User"

# Customer login/registration is phone+SMS-code only now (see
# apps/accounts/views.py) and never checks a password, so ModelBackend is
# only actually exercised for Django admin / staff logins.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# CompressedManifestStaticFilesStorage: whitenoise serves these with far-future
# cache headers safely, because each collectstatic run renames files with a
# content hash (site.abc123.css) — browsers/CDNs can cache "forever" without
# ever serving a stale file after a deploy. Requires `collectstatic` to be run
# after every deploy (it already was for STATIC_ROOT to have anything in it).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Serve user-uploaded product/category photos even with DEBUG=False.
# Whitenoise is for STATIC files (checked into the repo, known at deploy
# time); MEDIA files are uploaded at runtime through /admin/, so they can't
# be pre-hashed/collected the same way. django.views.static.serve is not as
# fast as Nginx under heavy concurrent load, but for a small/medium wholesale
# catalog (a few hundred products, not millions of requests/sec) it's fine
# and means media works without any extra web-server config. If traffic ever
# grows enough to matter, move MEDIA serving to Nginx or S3-compatible
# storage — see MEDIA_URL routing in config/urls.py.
SERVE_MEDIA_VIA_DJANGO = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    # Only enforced in production (DEBUG=False) so local development over
    # plain http://127.0.0.1:8000 keeps working without extra setup.
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Set BEHIND_PROXY=True in .env when deploying behind Nginx/Cloudflare with
# SSL terminated at the proxy. Without this, SECURE_SSL_REDIRECT above can't
# tell the original request was already HTTPS and causes a redirect loop.
if os.getenv("BEHIND_PROXY", "False") == "True":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CSRF_TRUSTED_ORIGINS is required by Django when the site is served over
# HTTPS behind a proxy/CDN on a real domain. Comma-separated full origins,
# e.g. CSRF_TRUSTED_ORIGINS=https://a.com,https://www.cicekdeposu.com
_csrf_trusted = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_trusted.split(",") if origin.strip()]

# --- Shared cache (rate limiting) ---------------------------------------
# LocMemCache is per-process: with 3 gunicorn workers every counter was split
# 3 ways and reset on restart, so the OTP/login limits were ~3x weaker than
# intended. Use Redis when REDIS_URL is set (docker-compose provides it),
# otherwise a DB-backed cache shared by all workers
# (run `python manage.py createcachetable` once).
_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _redis_url}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

# --- Client IP detection (used by apps/accounts/ratelimit.py) -------------
# Never trust X-Forwarded-For blindly: a client can send its own value.
# CLIENT_IP_HEADER: a header only your proxy can set, e.g. "CF-Connecting-IP"
#   behind Cloudflare. TRUSTED_PROXY_COUNT: how many proxies in front of the
#   app append to X-Forwarded-For (Nginx only = 1, Cloudflare + Nginx = 2).
CLIENT_IP_HEADER = os.getenv("CLIENT_IP_HEADER", "")
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))

# Hard daily ceiling on OTP messages (each one is billed by Meta).
OTP_DAILY_GLOBAL_MAX = int(os.getenv("OTP_DAILY_GLOBAL_MAX", "500"))

# Errors/warnings go to stdout (docker logs). Without this, DEBUG=False
# swallows most diagnostics. Optional Sentry: set SENTRY_DSN and
# `pip install sentry-sdk`.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {"django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
if os.getenv("SENTRY_DSN"):
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.0, send_default_pii=False)
    except ImportError:
        pass

MESSAGE_TAGS = {
    10: "debug",
    20: "info",
    25: "success",
    30: "warning",
    40: "error",
}

CART_SESSION_ID = "cart_id"

# --- WhatsApp Business Cloud API ---
# Used by apps.orders.whatsapp to notify the shop's WhatsApp when a new
# order comes in. See .env.example for where each value comes from.
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_ADMIN_PHONE = os.getenv("WHATSAPP_ADMIN_PHONE", "")
WHATSAPP_ORDER_TEMPLATE_NAME = os.getenv("WHATSAPP_ORDER_TEMPLATE_NAME", "new_order_alert")
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "tr")

# --- WhatsApp OTP (login/register one-time codes) ---
WHATSAPP_OTP_TEMPLATE_NAME = os.getenv("WHATSAPP_OTP_TEMPLATE_NAME", "login_code")

# Base URL used to build the order link sent inside the WhatsApp message
# (points staff to the admin page for that order). Set this to your real
# domain in production, e.g. https://cicekdeposu.com
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")

# --- Email ---
# No longer used by login/registration (that's phone + SMS code now, see
# apps.accounts.sms) — kept only because a couple of unwired Django
# auth views/templates for password reset still reference it, and because
# EMAIL_BACKEND must be set to *something*. If EMAIL_HOST/EMAIL_HOST_USER/
# EMAIL_HOST_PASSWORD aren't all set, this falls back to Django's console
# backend so nothing errors out.
_email_configured = all([
    os.getenv("EMAIL_HOST"),
    os.getenv("EMAIL_HOST_USER"),
    os.getenv("EMAIL_HOST_PASSWORD"),
])
if _email_configured:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@aspizflowers.com")

# Password reset links expire after this long (Django default is 3 days;
# kept explicit here so it's easy to find/tune).
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 3  # 3 days, in seconds
