"""Configuration Django de la plateforme de billetterie NovaTickets."""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Chargement optionnel du fichier .env -----------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv est optionnel
    pass


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "oui"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-novatickets-secret-a-changer")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["*"] if DEBUG else os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Apps NovaTickets
    "apps.core",
    "apps.accounts",
    "apps.events",
    "apps.tickets",
    "apps.payments",
    "apps.cards",
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
                "apps.core.context_processors.novatickets",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:redirection_tableau_de_bord"
LOGOUT_REDIRECT_URL = "core:accueil"

# --- E-mails ----------------------------------------------------------------
# En developpement : les e-mails sont ecrits dans la console ET dans /sent_emails
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_FILE_PATH = BASE_DIR / "sent_emails"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "NovaTickets <recus@novatickets.africa>")

# --- Reglages metier NovaTickets -------------------------------------------
NOVATICKETS = {
    "NOM": "NovaTickets",
    "BASELINE": "La billetterie evenementielle de l'Afrique de l'Ouest",
    "DEVISE": "FCFA",
    # Commission prelevee par la plateforme sur chaque ticket vendu.
    "COMMISSION_POURCENT": float(os.getenv("NOVATICKETS_COMMISSION_PERCENT", "5")),
    # Tarif unique de generation d'une carte de visite.
    "PRIX_CARTE_VISITE": int(os.getenv("NOVATICKETS_CARD_PRICE", "100")),
    # Provider de paiement actif : "simulation" en developpement.
    "PROVIDER_PAIEMENT": os.getenv("NOVATICKETS_PAYMENT_PROVIDER", "simulation"),
    "SUPPORT_EMAIL": "support@novatickets.africa",
    "BASE_URL": os.getenv("NOVATICKETS_BASE_URL", "http://localhost:8000"),
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
