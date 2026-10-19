"""Envoi des e-mails transactionnels (reçu d'achat, carte de visite prête)."""
import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.qr import qr_svg_data_uri

logger = logging.getLogger(__name__)


def envoyer_recu_commande(commande):
    """Reçu automatique, déclenché à la validation du paiement (voir services)."""
    premier = commande.tickets.select_related("type_ticket__evenement__organisateur").first()
    if premier is None:
        return
    evenement = premier.type_ticket.evenement
    acheteur = commande.acheteur
    lignes = []
    for ticket in commande.tickets.select_related("type_ticket"):
        lignes.append({
            "type": ticket.type_ticket.nom,
            "reference": ticket.reference,
            "prix": ticket.prix_unitaire,
            "nom": ticket.nom_titulaire,
        })

    contexte = {
        "commande": commande,
        "acheteur": acheteur,
        "evenement": evenement,
        "organisateur": evenement.organisateur,
        "lignes": lignes,
        "quantite": len(lignes),
        "prix_unitaire": premier.prix_unitaire,
        "total": commande.total,
        "statut_paiement": "Payé",
        "date_envoi": timezone.localtime(commande.payee_le or timezone.now()),
        "qr": qr_svg_data_uri(commande.reference),
        "base_url": settings.NOVATICKETS.get("BASE_URL", ""),
        "NT": settings.NOVATICKETS,
    }
    html = render_to_string("emails/recu_achat.html", contexte)
    texte = (
        f"Merci pour votre achat ! Événement : {evenement.nom}. "
        f"Référence : {commande.reference}. Total : {commande.total} FCFA."
    )
    message = EmailMultiAlternatives(
        subject=f"Votre reçu NovaTickets · {evenement.nom}",
        body=texte,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[acheteur.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=True)
    logger.info("Reçu envoyé à %s pour %s", acheteur.email, commande.reference)


def envoyer_carte_visite_prete(carte):
    """Notification simple quand la carte de visite est générée."""
    html = render_to_string("emails/carte_pret.html", {"carte": carte, "NT": settings.NOVATICKETS})
    message = EmailMultiAlternatives(
        subject="Votre carte de visite est prête",
        body="Votre carte de visite NovaTickets est prête à être téléchargée.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[carte.utilisateur.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=True)
