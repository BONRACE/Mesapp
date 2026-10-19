"""Comptes utilisateurs NovaTickets : spectateurs et organisateurs."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.core.countries import get_pays


class Role(models.TextChoices):
    SPECTATEUR = "spectateur", "Spectateur"
    ORGANISATEUR = "organisateur", "Organisateur"


class Sexe(models.TextChoices):
    HOMME = "H", "Homme"
    FEMME = "F", "Femme"
    AUTRE = "A", "Autre"


class User(AbstractUser):
    """Utilisateur unique pour les deux rôles.

    Les champs communs (pays, téléphone, identité) vivent ici ; les données
    propres aux organisateurs sont dans ProfilOrganisateur.
    """

    # On garde `username` d'AbstractUser mais l'e-mail est unique et sert
    # d'identifiant naturel côté interface.
    email = models.EmailField("adresse e-mail", unique=True)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.SPECTATEUR)

    first_name = models.CharField("prénoms", max_length=150)
    last_name = models.CharField("nom", max_length=150)
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices, blank=True)
    profession = models.CharField("profession", max_length=120, blank=True)
    photo = models.ImageField("photo de profil", upload_to="photos/", blank=True, null=True)

    pays = models.CharField("pays", max_length=2, default="BJ")
    indicatif = models.CharField("indicatif", max_length=6, default="+229")
    telephone = models.CharField("téléphone mobile", max_length=20)

    cree_le = models.DateTimeField("inscrit le", default=timezone.now)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.nom_complet} ({self.get_role_display()})"

    # -- Identité ----------------------------------------------------------
    @property
    def nom_complet(self):
        complet = f"{self.first_name} {self.last_name}".strip()
        return complet or self.username

    @property
    def initiales(self):
        prenom = (self.first_name or " ")[0]
        nom = (self.last_name or " ")[0]
        return (prenom + nom).upper().strip() or "NT"

    @property
    def objet_pays(self):
        return get_pays(self.pays)

    @property
    def telephone_complet(self):
        return f"{self.indicatif} {self.telephone}".strip()

    # -- Rôles -------------------------------------------------------------
    @property
    def est_organisateur(self):
        return self.role == Role.ORGANISATEUR

    @property
    def est_spectateur(self):
        return self.role == Role.SPECTATEUR

    # -- Finances (organisateur) -------------------------------------------
    @property
    def total_revenus_nets(self):
        """Somme des revenus nets (ventes - commission) sur ses événements."""
        from apps.tickets.models import Ticket

        total = (
            Ticket.objects.filter(
                type_ticket__evenement__organisateur=self,
                commande__statut="paye",
            ).aggregate(montant=Sum("montant_net_organisateur"))["montant"]
            or Decimal("0")
        )
        return Decimal(total)

    @property
    def total_retire(self):
        from apps.payments.models import Retrait

        total = (
            self.retraits.exclude(statut=Retrait.Statut.ECHOUE).aggregate(
                montant=Sum("montant")
            )["montant"]
            or Decimal("0")
        )
        return Decimal(total)

    @property
    def solde_disponible(self):
        """Solde retirable = revenus nets encaissés − retraits déjà engagés."""
        return self.total_revenus_nets - self.total_retire


class ProfilOrganisateur(models.Model):
    """Informations de la structure organisatrice (logo, signature, etc.)."""

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil_organisateur"
    )
    structure = models.CharField("nom de la structure", max_length=150)
    description = models.TextField("présentation", blank=True)
    logo = models.ImageField("logo de la structure", upload_to="organisateurs/logos/", blank=True, null=True)
    signature = models.ImageField(
        "signature scannée", upload_to="organisateurs/signatures/", blank=True, null=True
    )
    site_web = models.URLField("site web", blank=True)
    verifie = models.BooleanField("structure vérifiée", default=False)

    class Meta:
        verbose_name = "profil organisateur"
        verbose_name_plural = "profils organisateurs"

    def __str__(self):
        return self.structure

    @property
    def signature_texte(self):
        """Signature manuscrite de secours quand aucune image n'est fournie."""
        return self.structure
