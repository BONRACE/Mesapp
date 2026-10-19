"""Choix automatique du mode d'envoi des e-mails (testable sans charger les settings)."""

SMTP = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE = "django.core.mail.backends.console.EmailBackend"


def pick_backend(explicit: str, user: str, password: str, force_console: bool = False) -> str:
    """Règle :

    * un backend autre que « console » demandé explicitement est respecté ;
    * sinon, dès que EMAIL_HOST_USER **et** EMAIL_HOST_PASSWORD sont renseignés, on envoie
      réellement par SMTP (plus besoin de penser à changer EMAIL_BACKEND) ;
    * sinon, mode console (affichage dans le terminal, rien n'est envoyé).

    EMAIL_FORCE_CONSOLE=True permet de rester en console même avec des identifiants (tests).
    """
    explicit = (explicit or "").strip()
    if explicit and not explicit.endswith("console.EmailBackend"):
        return explicit
    if force_console:
        return CONSOLE
    if (user or "").strip() and (password or "").strip():
        return SMTP
    return CONSOLE


def clean_password(password: str, host: str) -> str:
    """Google affiche les mots de passe d'application par blocs de 4 séparés par des espaces."""
    if "gmail" in (host or "").lower() or "google" in (host or "").lower():
        return (password or "").replace(" ", "")
    return password or ""


def default_sender(explicit: str, platform_name: str, user: str) -> str:
    """Expéditeur : celui du .env, sinon l'adresse du compte SMTP (Gmail refuse un autre expéditeur)."""
    if explicit.strip():
        return explicit.strip()
    if (user or "").strip():
        return f"{platform_name} <{user.strip()}>"
    return f"{platform_name} <no-reply@novatickets.app>"
