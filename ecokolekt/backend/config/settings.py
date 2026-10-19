"""EcoKolekt — configuration Django (PostgreSQL + PostGIS)."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "accounts",
    "waste",
    "routing",
    "marketplace",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("POSTGRES_DB", "ecokolekt"),
        "USER": env("POSTGRES_USER", "ecokolekt"),
        "PASSWORD": env("POSTGRES_PASSWORD", "ecokolekt"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- API -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"otp_request": "10/hour", "otp_verify": "30/hour"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {"TITLE": "EcoKolekt API", "VERSION": "1.0.0"}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = [o for o in env("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",") if o]
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# --- OTP / SMS -------------------------------------------------------------
OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_PER_HOUR = 5
OTP_MAX_ATTEMPTS = 5
SMS_BACKEND = env("SMS_BACKEND", "console")  # console | http
SMS_HTTP_URL = env("SMS_HTTP_URL", "")
SMS_HTTP_TOKEN = env("SMS_HTTP_TOKEN", "")
SMS_SENDER = env("SMS_SENDER", "EcoKolekt")
DEFAULT_PHONE_REGION = "BJ"
# Démo : les collecteurs/recycleurs sont approuvés automatiquement. À mettre à False en production.
AUTO_APPROVE_PROFESSIONALS = env_bool("AUTO_APPROVE_PROFESSIONALS", DEBUG)

# --- QR sécurisés ----------------------------------------------------------
QR_SIGNING_KEY = env("QR_SIGNING_KEY", SECRET_KEY)
QR_MAX_DISTANCE_M = int(env("QR_MAX_DISTANCE_M", "250"))  # le collecteur doit être près du ménage

# --- Routage ---------------------------------------------------------------
OSRM_URL = env("OSRM_URL", "")  # ex. http://osrm:5000 ; vide = estimation haversine
ROUTING_AVG_SPEED_KMH = float(env("ROUTING_AVG_SPEED_KMH", "22"))
ROUTING_SERVICE_TIME_S = int(env("ROUTING_SERVICE_TIME_S", "240"))
AUTO_ASSIGN_RADIUS_M = int(env("AUTO_ASSIGN_RADIUS_M", "6000"))

# --- Marché & paiements ----------------------------------------------------
MARKET_COMMISSION_RATE = env("MARKET_COMMISSION_RATE", "0.05")
ORDER_PAYMENT_TTL_MINUTES = 30
PAYMENT_DEFAULT_PROVIDER = env("PAYMENT_DEFAULT_PROVIDER", "mock")  # mock | fedapay | cinetpay
FEDAPAY_SECRET_KEY = env("FEDAPAY_SECRET_KEY", "")
FEDAPAY_WEBHOOK_SECRET = env("FEDAPAY_WEBHOOK_SECRET", "")
FEDAPAY_ENV = env("FEDAPAY_ENV", "sandbox")  # sandbox | live
CINETPAY_API_KEY = env("CINETPAY_API_KEY", "")
CINETPAY_SITE_ID = env("CINETPAY_SITE_ID", "")
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:8080")
BACKEND_URL = env("BACKEND_URL", "http://localhost:8000")  # URL publique de l'API (notify_url des passerelles)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# --- Garde-fous de production ----------------------------------------------
# Avec DJANGO_DEBUG=0, le démarrage échoue plutôt que de tourner avec une configuration de démonstration.
if not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    _problems = []
    if SECRET_KEY.startswith("dev-insecure") or len(SECRET_KEY) < 32:
        _problems.append("DJANGO_SECRET_KEY : définissez une clé secrète aléatoire d'au moins 32 caractères.")
    if ALLOWED_HOSTS == ["*"]:
        _problems.append("DJANGO_ALLOWED_HOSTS : listez explicitement vos domaines.")
    if SMS_BACKEND == "console":
        _problems.append("SMS_BACKEND=console écrit les codes OTP dans les logs : utilisez SMS_BACKEND=http.")
    if PAYMENT_DEFAULT_PROVIDER == "mock":
        _problems.append("PAYMENT_DEFAULT_PROVIDER=mock valide des paiements fictifs : utilisez fedapay ou cinetpay.")
    if _problems:
        raise ImproperlyConfigured("Configuration de production invalide :\n - " + "\n - ".join(_problems))
