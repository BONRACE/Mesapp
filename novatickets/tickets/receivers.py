"""Branchement sur la fin de paiement : émission des tickets puis envoi du reçu."""
import logging

from django.db import transaction
from django.dispatch import receiver

from payments.signals import payment_succeeded

from . import services
from .emails import send_receipt

log = logging.getLogger(__name__)


@receiver(payment_succeeded, dispatch_uid="tickets.issue_and_email")
def on_payment_succeeded(sender, payment, **kwargs):
    if not payment.order_id:
        return
    services.issue_tickets(payment)  # peut lever FulfilmentError → paiement remboursé
    order_id = payment.order_id

    def _send():
        from .models import Order

        try:
            send_receipt(Order.objects.get(pk=order_id), payment)
        except Exception:  # un échec d'e-mail ne doit jamais annuler un achat
            log.exception("Envoi du reçu impossible pour la commande %s", order_id)

    # Après validation de la transaction : le reçu n'est envoyé que si tout est enregistré.
    transaction.on_commit(_send)
