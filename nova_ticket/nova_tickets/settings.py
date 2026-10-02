"""
Django settings for NovaTickets — plateforme de billetterie événementielle.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Charge les variables du fichier .env (à la racine du projet, à côté de manage.py) dans
# l'environnement, s'il existe. En production, ces variables peuvent aussi être définies
# directement au niveau du système/serveur — load_dotenv() ne les écrase pas dans ce cas.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "events",
    "tickets",
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

ROOT_URLCONF = "nova_tickets.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "nova_tickets.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard_redirect"
LOGOUT_REDIRECT_URL = "home"

# Commission prélevée par la plateforme sur chaque billet vendu (en pourcentage du prix),
# appliquée uniquement aux organisateurs en plan FREE (voir accounts.models.PlanAbonnement).
PLATFORM_COMMISSION_PERCENT = 5

# Abonnement Pro (0% de commission) — prix en FCFA, équivalent affiché de 50 $US.
PLAN_PRO_PRIX_FCFA = 30000
PLAN_PRO_PRIX_USD_AFFICHE = 50
PLAN_PRO_DUREE_JOURS = 30

# Abonnement "Pro" (0% de commission) — prix affiché à l'organisateur
PLATFORM_PRO_PLAN_PRICE_USD = 50
PLATFORM_PRO_PLAN_DURATION_DAYS = 30

# URL de base publique du site, utilisée pour construire les liens de callback et de webhook
# envoyés à FedaPay (doit être une URL HTTPS accessible depuis Internet en production).
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://127.0.0.1:8000")

# --- FedaPay (passerelle de paiement) ---
# Clés à récupérer sur https://dashboard.fedapay.com (Développeurs > Clés API)
# et le secret de webhook sur Développeurs > Webhooks > votre endpoint.
# Ne jamais committer de vraies clés : elles doivent venir de variables d'environnement.
FEDAPAY_ENVIRONMENT = os.environ.get("FEDAPAY_ENVIRONMENT", "sandbox")  # "sandbox" ou "live"
FEDAPAY_SECRET_KEY = os.environ.get("FEDAPAY_SECRET_KEY", "")
FEDAPAY_PUBLIC_KEY = os.environ.get("FEDAPAY_PUBLIC_KEY", "")
FEDAPAY_WEBHOOK_SECRET = os.environ.get("FEDAPAY_WEBHOOK_SECRET", "")
FEDAPAY_API_BASE = (
    "https://api.fedapay.com/v1" if FEDAPAY_ENVIRONMENT == "live"
    else "https://sandbox-api.fedapay.com/v1"
)

# E-mail — mode développement : les messages s'affichent dans la console au lieu d'être
# réellement envoyés. Remplacer par un backend SMTP réel en production.
# E-mail — par défaut, les messages s'affichent dans la console (développement). En production,
# définis EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend dans le .env, avec les
# identifiants SMTP de ton fournisseur (SendGrid, Mailgun, Brevo, etc.).
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "NovaTickets <no-reply@novatickets.bj>")
