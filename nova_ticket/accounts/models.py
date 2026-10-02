from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Utilisateur unique de la plateforme : soit spectateur, soit organisateur."""

    class Role(models.TextChoices):
        SPECTATEUR = "spectateur", "Spectateur"
        ORGANISATEUR = "organisateur", "Organisateur"

    class Sexe(models.TextChoices):
        HOMME = "H", "Homme"
        FEMME = "F", "Femme"
        AUTRE = "X", "Autre / Préfère ne pas dire"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SPECTATEUR)

    # Champs communs demandés : nom, prénoms, sexe, profession, photo
    nom = models.CharField(max_length=100, blank=True)
    prenoms = models.CharField(max_length=150, blank=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    profession = models.CharField(max_length=150, blank=True)
    photo = models.ImageField(upload_to="avatars/", blank=True, null=True)
    telephone = models.CharField(max_length=30, blank=True)
    pays = models.CharField(max_length=100, blank=True, default="Bénin")

    # Champs spécifiques organisateur
    nom_structure = models.CharField(max_length=150, blank=True)
    logo_organisateur = models.ImageField(upload_to="logos_organisateurs/", blank=True, null=True)

    @property
    def nom_complet(self):
        return f"{self.prenoms} {self.nom}".strip() or self.username

    @property
    def is_organisateur(self):
        return self.role == self.Role.ORGANISATEUR

    def __str__(self):
        return self.nom_complet


class PlanAbonnement(models.Model):
    """Plan tarifaire (Freemium) d'un organisateur : Gratuit (commission) ou Pro (abonnement, 0% commission)."""

    class Plan(models.TextChoices):
        FREE = "FREE", "Gratuit"
        PRO = "PRO", "Pro"

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        EXPIRE = "expire", "Expiré"
        ANNULE = "annule", "Annulé"

    organisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                         related_name="abonnement")
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ACTIF)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(null=True, blank=True,
                                            help_text="Fin de la période payée en cours (plan PRO uniquement).")

    # Référence à la transaction FedaPay ayant payé le dernier renouvellement de l'abonnement Pro
    fedapay_transaction_id = models.CharField(max_length=40, blank=True, null=True, db_index=True)

    class Meta:
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"

    def __str__(self):
        return f"{self.organisateur.nom_complet} — {self.get_plan_display()}"

    def est_pro_actif(self):
        """True si l'organisateur bénéficie actuellement du 0% de commission (abonnement Pro payé et non expiré)."""
        if self.plan != self.Plan.PRO or self.statut != self.Statut.ACTIF:
            return False
        return bool(self.date_expiration) and self.date_expiration >= timezone.now()

    def commission_pourcentage(self):
        """Pourcentage de commission plateforme applicable pour cet organisateur, selon son plan."""
        if self.est_pro_actif():
            return 0
        return settings.PLATFORM_COMMISSION_PERCENT

    @classmethod
    def pour(cls, organisateur):
        """Récupère (ou crée) le plan de l'organisateur donné — tout organisateur démarre en FREE."""
        plan, _ = cls.objects.get_or_create(organisateur=organisateur)
        return plan
