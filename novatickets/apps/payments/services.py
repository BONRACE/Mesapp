"""Logique métier de paiement : commission, création des billets, reçus.

Règles clés :
- commission = prix × taux (configurable) ; net organisateur = prix − commission ;
- un organisateur ne peut pas acheter pour SES propres événements ;
- le stock est vérifié et réservé dans une transaction atomique ;
- à la validation du paiement, les billets sont émis et le reçu part par e-mail.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.events.models import TypeTicket
from apps.tickets.models import Commande, Ticket

from .models import Paiement
from .providers import get_provider


def calculer_commission(prix, taux=None):
    """Retourne (commission, net) en FCFA entiers."""
    taux = Decimal(str(taux if taux is not None else settings.NOVATICKETS["COMMISSION_POURCENT"]))
    prix = Decimal(prix)
    commission = (prix * taux / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return commission, prix - commission


class PanierItem:
    def __init__(self, type_ticket, quantite, beneficiaire=None):
        self.type_ticket = type_ticket
        self.quantite = quantite
        # beneficiaire : dict {prenom, nom, contact, sexe} ou None (pour soi-même)
        self.beneficiaire = beneficiaire


def verifier_eligibilite(acheteur, type_ticket):
    """Règles d'achat : pas ses propres événements, événement ouvert, stock."""
    evenement = type_ticket.evenement
    if acheteur.est_organisateur and evenement.organisateur_id == acheteur.id:
        raise ValidationError("Vous ne pouvez pas acheter de tickets pour vos propres événements.")
    if not evenement.achats_ouverts:
        raise ValidationError(f"Les achats pour « {evenement.nom} » sont fermés.")


@transaction.atomic
def creer_commande(acheteur, items, moyen):
    """Crée la commande et réserve les tickets (en attente de paiement)."""
    if not items:
        raise ValidationError("Votre panier est vide.")
    commande = Commande.objects.create(acheteur=acheteur)
    total = Decimal("0")

    for item in items:
        tt = TypeTicket.objects.select_for_update().select_related("evenement").get(pk=item.type_ticket.pk)
        verifier_eligibilite(acheteur, tt)
        if item.quantite < 1:
            raise ValidationError("La quantité doit être au moins 1.")
        if tt.restants < item.quantite:
            raise ValidationError(f"Stock insuffisant pour « {tt.nom} » ({tt.restants} restant(s)).")

        for _ in range(item.quantite):
            commission, net = calculer_commission(tt.prix)
            benef = item.beneficiaire or {}
            ticket = Ticket(
                commande=commande,
                type_ticket=tt,
                titulaire=acheteur,
                prix_unitaire=tt.prix,
                commission=commission,
                montant_net_organisateur=net,
            )
            # Réservation pour un ami : le ticket est nominatif à son nom.
            if benef.get("prenom") or benef.get("nom"):
                ticket.beneficiaire_prenom = benef.get("prenom", "")
                ticket.beneficiaire_nom = benef.get("nom", "")
                ticket.beneficiaire_contact = benef.get("contact", "")
                ticket.beneficiaire_sexe = benef.get("sexe", "")
            ticket.save()
            total += Decimal(tt.prix)

    commande.total = total
    commande.mode_paiement = moyen
    commande.save(update_fields=["total", "mode_paiement"])
    return commande


@transaction.atomic
def lancer_paiement(commande, moyen_slug, telephone=""):
    """Crée le Paiement et interroge le provider choisi."""
    provider = get_provider(moyen_slug)
    if provider is None:
        raise ValidationError("Ce moyen de paiement n'est pas disponible.")
    paiement = Paiement.objects.create(
        utilisateur=commande.acheteur,
        objet=Paiement.Objet.COMMANDE,
        commande=commande,
        montant=commande.total,
        commission=sum((t.commission for t in commande.tickets.all()), Decimal("0")),
        fournisseur=provider.slug,
        telephone_payeur=telephone,
    )
    resultat = provider.initier(paiement, telephone)
    if resultat.succes:
        paiement.reference_externe = resultat.reference_externe
        paiement.save(update_fields=["reference_externe"])
        confirmer_paiement(paiement)
    else:
        # La commande reste « en attente » : les billets restent réservés
        # et l'acheteur peut réessayer avec un autre moyen.
        paiement.statut = Paiement.Statut.ECHOUE
        paiement.save(update_fields=["statut"])
    return paiement


@transaction.atomic
def confirmer_paiement(paiement):
    """Point d'entrée unique « paiement validé » : marque la commande payée,
    puis déclenche l'envoi automatique du reçu après commit."""
    if paiement.statut == Paiement.Statut.REUSSI:
        return paiement  # idempotent : un webhook rejoué ne renvoie pas le reçu deux fois
    paiement.statut = Paiement.Statut.REUSSI
    paiement.termine_le = timezone.now()
    paiement.save(update_fields=["statut", "termine_le"])

    commande = paiement.commande
    if commande:
        commande.statut = Commande.Statut.PAYE
        commande.payee_le = timezone.now()
        commande.save(update_fields=["statut", "payee_le"])
        # Import local pour éviter les cycles d'import au démarrage.
        from apps.core.emails import envoyer_recu_commande

        transaction.on_commit(lambda: envoyer_recu_commande(commande))
    return paiement
