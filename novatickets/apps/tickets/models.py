"""Commandes et billets."""
import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.events.models import TypeTicket


def generer_reference(prefixe, longueur=8):
    alphabet = string.ascii_uppercase + string.digits
    return prefixe + "".join(secrets.choice(alphabet) for _ in range(longueur))


class Commande(models.Model):
    """Achat groupé : un acheteur, un ou plusieurs tickets, un paiement."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente de paiement"
        PAYE = "paye", "Payée"
        ECHOUE = "echec", "Échouée"
        REMBOURSE = "rembourse", "Remboursée"

    reference = models.CharField(max_length=20, unique=True, default=lambda: generer_reference("CMD-"))
    acheteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commandes_achetees"
    )
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    mode_paiement = models.CharField(max_length=40, blank=True)
    creee_le = models.DateTimeField(default=timezone.now)
    payee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creee_le"]

    def __str__(self):
        return self.reference

    @property
    def est_payee(self):
        return self.statut == self.Statut.PAYE


class Ticket(models.Model):
    """Un billet nominatif. Il peut être émis pour un ami (beneficiaire_*)."""

    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="tickets")
    type_ticket = models.ForeignKey(TypeTicket, on_delete=models.PROTECT, related_name="tickets")
    # Titulaire réel du billet : l'acheteur, ou l'ami si la réservation est pour lui.
    titulaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets_detenus", null=True, blank=True
    )
    beneficiaire_prenom = models.CharField(max_length=150, blank=True)
    beneficiaire_nom = models.CharField(max_length=150, blank=True)
    beneficiaire_contact = models.CharField("e-mail ou téléphone", max_length=190, blank=True)
    beneficiaire_sexe = models.CharField(max_length=1, blank=True)
    reference = models.CharField(max_length=20, unique=True, default=lambda: generer_reference("NT-"))
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=0)
    commission = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    montant_net_organisateur = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    utilise = models.BooleanField(default=False)
    emis_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-emis_le"]

    def __str__(self):
        return f"{self.reference} · {self.nom_titulaire}"

    @property
    def evenement(self):
        return self.type_ticket.evenement

    @property
    def nom_titulaire(self):
        if self.beneficiaire_nom or self.beneficiaire_prenom:
            return f"{self.beneficiaire_prenom} {self.beneficiaire_nom}".strip()
        return self.titulaire.nom_complet if self.titulaire else "—"

    @property
    def est_pour_ami(self):
        return bool(self.titulaire and self.commande.acheteur_id != self.titulaire_id)

    @property
    def sexe_titulaire(self):
        if self.beneficiaire_sexe:
            return self.beneficiaire_sexe
        if self.est_pour_ami or not self.titulaire:
            return ""
        return self.titulaire.sexe

    @property
    def sexe_libelle(self):
        from apps.accounts.models import Sexe

        return dict(Sexe.choices).get(self.sexe_titulaire, "—")

    @property
    def photo_titulaire(self):
        # Pour un ami, on n'affiche jamais la photo de l'acheteur.
        if self.est_pour_ami or not self.titulaire or not self.titulaire.photo:
            return None
        return self.titulaire.photo

    @property
    def est_valide(self):
        return self.commande.est_payee and not self.utilise and self.evenement.date_fin >= timezone.localdate()
