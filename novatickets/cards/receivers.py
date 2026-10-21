"""Active la carte dès que son paiement de 100 FCFA est validé."""
from django.dispatch import receiver
from django.utils import timezone

from payments.signals import payment_succeeded


@receiver(payment_succeeded, dispatch_uid="cards.activate")
def activate_card(sender, payment, **kwargs):
    card = payment.business_card
    if card and not card.is_paid:
        card.is_paid, card.paid_at = True, timezone.now()
        card.save(update_fields=["is_paid", "paid_at"])
