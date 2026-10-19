"""E-mail de confirmation après paiement d'une carte de visite : récapitulatif + PDF d'impression en pièce jointe."""
import io

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from orders.services import _inline, _logo_bytes, _send, _social_links, email_is_console

from . import cards
from .models import CardPayment


def send_card_receipt(payment: CardPayment):
    """Retourne True si le message est parti."""
    user, card = payment.user, payment.card
    if not user.email:
        return False
    text = (f"Merci {user.first_name or user.username} !\nVotre carte de visite « {card.company_name} » est prête.\n"
            f"Référence : {payment.reference} · {payment.amount} FCFA\n"
            f"Le PDF d'impression est en pièce jointe. Retrouvez aussi vos cartes : {settings.SITE_URL}/carte-de-visite/{card.pk}/")
    msg = EmailMultiAlternatives(f"Votre carte de visite est prête – {card.company_name}", text,
                                 settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.mixed_subtype = "related"
    _inline(msg, "logo", _logo_bytes("logo-full.png"))
    recto = cards.final_image(card, "recto").resize((700, 400))
    buf = io.BytesIO()
    recto.save(buf, "JPEG", quality=90)
    has_card = _inline(msg, "cardrecto", buf.getvalue(), "jpeg")
    ctx = {"payment": payment, "card": card, "user": user, "has_card": has_card,
           "card_url": f"{settings.SITE_URL}{card.get_absolute_url()}", "social_links": _social_links()}
    msg.attach_alternative(render_to_string("emails/card_receipt.html", ctx), "text/html")
    msg.attach(f"carte-de-visite-{card.pk}.pdf", cards.card_pdf(card), "application/pdf")
    ok = _send(msg)
    if ok and not email_is_console():
        payment.receipt_sent_at = timezone.now()
        CardPayment.objects.filter(pk=payment.pk).update(receipt_sent_at=payment.receipt_sent_at)
    return ok
