"""Envoi automatique du reçu de paiement par e-mail après achat d'un billet."""
import os

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .utils import generate_qr_bytes

PLATFORM_LOGO = settings.BASE_DIR / "static" / "img" / "logo-horizontal.png"


class RecuEmail(EmailMultiAlternatives):
    """E-mail HTML avec images intégrées (multipart/related, référencées par src="cid:...").

    Django ne gère plus nativement les images inline : on les rattache à la partie HTML
    avec l'API standard de Python (add_related).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inline_images = []  # [(bytes, subtype, cid, filename)]

    def add_inline_image(self, path, cid):
        path = str(path)
        with open(path, "rb") as f:
            data = f.read()
        subtype = os.path.splitext(path)[1].lstrip(".").lower().replace("jpg", "jpeg") or "png"
        self.inline_images.append((data, subtype, cid, os.path.basename(path)))

    def add_inline_image_bytes(self, data, cid, subtype="png", filename=None):
        self.inline_images.append((data, subtype, cid, filename or f"{cid}.{subtype}"))

    def message(self, *args, **kwargs):
        msg = super().message(*args, **kwargs)
        html_part = msg.get_body(preferencelist=("html",))
        if html_part is not None:
            for data, subtype, cid, filename in self.inline_images:
                html_part.add_related(data, "image", subtype, cid=f"<{cid}>",
                                      filename=filename, disposition="inline")
        return msg


def _event_logo_path(event):
    logo = event.logo_effectif
    try:
        if logo and os.path.exists(logo.path):
            return logo.path
    except (ValueError, NotImplementedError):
        pass
    return None


def envoyer_recu_billet(ticket):
    """Envoie un reçu de paiement par e-mail au spectateur pour le billet donné."""
    event = ticket.event
    spectateur = ticket.spectateur

    if not spectateur.email:
        return False

    event_logo = _event_logo_path(event)
    contexte = {
        "ticket": ticket, "event": event, "spectateur": spectateur,
        "has_event_logo": bool(event_logo),
    }
    html_content = render_to_string("tickets/emails/recu_billet.html", contexte)
    text_content = strip_tags(html_content)

    sujet = f"Votre billet pour {event.nom} — NovaTickets"
    message = RecuEmail(
        subject=sujet,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[spectateur.email],
    )
    message.attach_alternative(html_content, "text/html")
    message.add_inline_image(PLATFORM_LOGO, "logo_nova")
    if event_logo:
        message.add_inline_image(event_logo, "logo_event")
    message.add_inline_image_bytes(generate_qr_bytes(ticket.qr_payload), "ticket_qr")
    message.send(fail_silently=True)
    return True
