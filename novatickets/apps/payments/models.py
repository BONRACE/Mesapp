"""Paiements, retraits et cartes de visite payées."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tickets.models import generer_reference


class Paiement(models.Model):
    """Transaction associée à une commande (ticket) ou à une carte de visite."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        REUSSI = "reussi", "Réussi"
        ECHOUE = "echoue", "Échoué"

    class Objet(models.TextChoices):
        COMMANDE = "commande", "Billetterie"
        CARTE = "carte", "Carte de visite"

    reference = models.CharField(max_length=32, unique=True, default=lambda: generer_reference("PAY-", 12))
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="paiements")
    objet = models.CharField(max_length=12, choices=Objet.choices)
    commande = models.ForeignKey(
        "tickets.Commande", on_delete=models.PROTECT, null=True, blank=True, related_name="paiements"
    )
    montant = models.DecimalField(max_digits=12, decimal_places=0)
    commission = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    fournisseur = models.CharField("moyen de paiement", max_length=40)
    reference_externe = models.CharField("référence chez l'opérateur", max_length=64, blank=True)
    telephone_payeur = models.CharField(max_length=30, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    cree_le = models.DateTimeField(default=timezone.now)
    termine_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.reference} · {self.montant} FCFA"


class Retrait(models.Model):
    """Demande de retrait des gains d'un organisateur vers un moyen local."""

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        PAYE = "paye", "Versé"
        ECHOUE = "echoue", "Échoué"

    organisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="retraits")
    montant = models.DecimalField(max_digits=12, decimal_places=0)
    moyen = models.CharField("moyen de retrait", max_length=40)
    numero_compte = models.CharField("numéro de compte", max_length=30)
    reference = models.CharField(max_length=32, unique=True, default=lambda: generer_reference("RET-", 10))
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_COURS)
    demande_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-demande_le"]

    def __str__(self):
        return f"{self.reference} · {self.montant} FCFA"
