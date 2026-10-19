import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Les réglages sensibles viennent du fichier .env (voir .env.example).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv non installé : on lit seulement les variables du système
    pass


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "on", "oui")


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# ------------------------------------------------------------------ Sécurité
DEBUG = env_bool("DEBUG", True)
SECRET_KEY = env("SECRET_KEY", "dev-only-change-me-in-production")
if not DEBUG and SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("Définissez une SECRET_KEY secrète dans .env avant de passer DEBUG=False.")

# En développement on accepte tout (pratique pour tester depuis un smartphone sur le même Wi-Fi).
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*" if DEBUG else "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("COOKIE_SECURE", True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "events",
    "orders",
    "core",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.platform",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------------ Base de données
# SQLite par défaut ; PostgreSQL si DB_ENGINE=postgres (pip install "psycopg[binary]").
if env("DB_ENGINE", "sqlite").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "novatickets"),
            "USER": env("DB_USER", "postgres"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / env("DB_NAME", "db.sqlite3"),
        }
    }

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard_redirect"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = env("TIME_ZONE", "Africa/Porto-Novo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # destination de `collectstatic` en production
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ E-mails
# Envoi automatique : il suffit de renseigner EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans .env.
# Sans identifiants, les e-mails s'affichent seulement dans le terminal (mode « console »).
from .mailconf import clean_password, default_sender, pick_backend  # noqa: E402

PLATFORM_NAME = env("PLATFORM_NAME", "NovaTickets")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER").strip()
EMAIL_HOST_PASSWORD = clean_password(env("EMAIL_HOST_PASSWORD").strip(), EMAIL_HOST)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "15"))  # secondes : évite de bloquer la page si le serveur ne répond pas
EMAIL_BACKEND = pick_backend(env("EMAIL_BACKEND"), EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, env_bool("EMAIL_FORCE_CONSOLE", False))
DEFAULT_FROM_EMAIL = default_sender(env("DEFAULT_FROM_EMAIL"), PLATFORM_NAME, EMAIL_HOST_USER)

# ------------------------------------------------------------------ Plateforme
# Prix (FCFA) pour générer une carte de visite
BUSINESS_CARD_PRICE = int(env("BUSINESS_CARD_PRICE", "100"))
PLATFORM_COMMISSION_RATE = float(env("PLATFORM_COMMISSION_RATE", "0.05"))  # 0.05 = 5 % par ticket vendu
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000").rstrip("/")  # utilisé dans les QR codes et les e-mails
# Liens réseaux sociaux affichés en bas des e-mails (vide = masqué)
SOCIAL_LINKS = {
    "Facebook": env("SOCIAL_FACEBOOK"),
    "Instagram": env("SOCIAL_INSTAGRAM"),
    "X": env("SOCIAL_X"),
}
