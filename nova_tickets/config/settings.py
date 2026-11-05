import os
from pathlib import Path
import environ
import logging
import sys
from decimal import Decimal
from pathlib import Path

from .env import env, env_bool, env_int, env_list, load_env

BASE_DIR = Path(__file__).resolve().parent.parent
load_env(BASE_DIR / ".env")        # variables d'environnement : voir .env.example
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me-novatickets")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "events",
    "orders",
    "payments",
    "scanner",
    "cards",
    "analytics",
    "payouts",
    "subscriptions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]   # connexion par e-mail OU nom d'utilisateur
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "core.storage.VersionedStaticStorage"},  # ajoute ?v=<mtime> : plus de CSS périmé en cache
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
PASSWORD_RESET_TIMEOUT = 3600  # le lien « mot de passe oublié » expire au bout d'1 heure
LOGOUT_REDIRECT_URL = "core:home"

# --- Configuration générale, e-mails et métadonnées ---
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.filebased.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="NovaTickets <bonracedolivierk@gmail.com>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_FILE_PATH = BASE_DIR / "sent_emails"

SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="contact@novatickets.app")
LEGAL_COMPANY = env("LEGAL_COMPANY", default="NovaTickets — Cotonou, République du Bénin")

MOMO_GATEWAY_MODE = env("MOMO_GATEWAY_MODE", default="simulation")

# Garde-fou anti-panique SMTP
_EMAIL_PLACEHOLDERS = {"", "bonracedolivierk@gmail.com", "46037368Bn", "remplacez-moi"}

if EMAIL_BACKEND.endswith("smtp.EmailBackend") and (
    EMAIL_HOST_USER in _EMAIL_PLACEHOLDERS or EMAIL_HOST_PASSWORD in _EMAIL_PLACEHOLDERS
):
    logging.getLogger(__name__).warning(
        "EMAIL_HOST_USER / EMAIL_HOST_PASSWORD non renseignés ou invalides dans .env : les e-mails sont écrits dans sent_emails/."
    )
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"    
# Plateforme
PLATFORM_NAME = "NovaTickets"
PLATFORM_COMMISSION_PERCENT = Decimal("2.5")  # commission : exactement 2,5 % du prix de chaque billet vendu
CURRENCY = "FCFA"
SUBSCRIPTION_PRICE = 5000        # abonnement organisateur (FCFA)
SUBSCRIPTION_DAYS = 30           # durée d'une période payée
SUBSCRIPTION_REQUIRED = env_bool("SUBSCRIPTION_REQUIRED", False)  # True : abonnement actif exigé pour créer / publier un événement
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="contact@novatickets.app")
LEGAL_COMPANY = env("LEGAL_COMPANY", default="NovaTickets — Cotonou, République du Bénin")
# Pages de la plateforme sur les réseaux (icônes du reçu). Vide = lien vers le site.
SOCIAL_LINKS = {"x": "", "facebook": "", "instagram": ""}
MIN_WITHDRAWAL = 1000

# --- Module de paiement Mobile Money (app payments) ---
MOMO_GATEWAY_MODE = env("MOMO_GATEWAY_MODE", default="simulation")
MOMO_API_BASE_URL = env("MOMO_API_BASE_URL", "")            # URL de l'API de l'agrégateur (mode live)
MOMO_API_KEY = env("MOMO_API_KEY", "")                      # clé API de l'agrégateur
MOMO_WEBHOOK_SECRET = env("MOMO_WEBHOOK_SECRET", "dev-secret-a-changer")  # secret partagé du webhook (HMAC-SHA256)
MOMO_CURRENCY = "XOF"
MOMO_MIN_AMOUNT = 100
MOMO_MAX_AMOUNT = 2_000_000

# --- Cartes de visite numériques ---
BUSINESS_CARD_PRICE = 100   # FCFA, payés en Mobile Money pour activer le partage public d'une carte (0 = gratuit)

# Tests plus rapides : hachage de mot de passe léger uniquement quand on lance `manage.py test`.
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
