from django.dispatch import Signal

# Émis (dans la transaction) dès qu'un paiement est validé. Argument : `payment`.
# C'est le point d'accroche unique : émission des tickets, e-mail de reçu,
# activation d'une carte de visite… sans aucune action manuelle.
payment_succeeded = Signal()


class FulfilmentError(Exception):
    """Levée par un récepteur quand la commande ne peut plus être honorée (ex. stock épuisé)."""
