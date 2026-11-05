"""Suppression de compte (spectateur ou organisateur).

Les commandes, billets et retraits doivent rester en base (comptabilité, remboursements, contrôle d'entrée) :
le compte est donc ANONYMISÉ et désactivé plutôt qu'effacé. Toutes les données personnelles sont retirées
(nom, e-mail, téléphone, photo, logo, carte de visite, moyens de retrait) et la connexion devient impossible.
"""
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.services import organizer_balance

CONFIRM_WORD = "SUPPRIMER"


def blockers(user):
    """Raisons qui empêchent de supprimer le compte maintenant : liste de (message, lien d'action, libellé du lien).

    Liste vide = suppression possible.
    """
    from django.urls import reverse

    reasons = []
    if user.is_organizer:
        if organizer_balance(user) > 0:
            reasons.append(("Il vous reste un solde à retirer : retirez vos fonds avant de supprimer le compte.", reverse("events:withdraw"), "Retirer mes fonds"))
        upcoming = Order.objects.filter(event__organizer=user, status=Order.Status.PAID, event__end_date__gte=timezone.localdate())
        if upcoming.exists():
            reasons.append(("Des billets ont été vendus pour un événement à venir ou en cours : attendez la fin de l'événement pour supprimer votre compte.", reverse("events:orga_dashboard"), "Voir mes événements"))
        if Order.objects.filter(event__organizer=user, status=Order.Status.NEEDS_REFUND).exists():
            reasons.append(("Des commandes sont à rembourser : traitez-les d'abord.", reverse("events:orga_dashboard"), "Voir mon tableau de bord"))
    return reasons


@transaction.atomic
def delete_account(user):
    """Anonymise et désactive le compte. Renvoie False si une raison l'interdit (rien n'est modifié)."""
    if blockers(user):
        return False
    for field in ("photo", "org_logo", "signature_image"):
        f = getattr(user, field)
        if f:
            f.delete(save=False)
    if hasattr(user, "business_card"):
        user.business_card.delete()
    user.payout_methods.all().delete()
    user.events.filter(is_published=True).update(is_published=False)
    user.first_name, user.last_name = "Compte", "supprimé"
    user.email, user.username = f"supprime-{user.pk}@deleted.invalid", f"supprime-{user.pk}"
    user.phone = user.profession = user.org_name = user.signature = ""
    user.sexe = ""
    user.signature_mode = user.SignatureMode.ORGANIZER
    user.is_active = False
    user.set_unusable_password()
    user.save()
    return True
