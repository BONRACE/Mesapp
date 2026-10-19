"""Événements, types de tickets et gestion des visuels."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Evenement(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        PUBLIE = "publie", "Publié"
        ANNULE = "annule", "Annulé"

    organisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="evenements",
        limit_choices_to={"role": "organisateur"},
    )
    nom = models.CharField("nom de l'événement", max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField("description", blank=True)
    visuel = models.ImageField("visuel de l'événement", upload_to="evenements/visuels/", blank=True, null=True)
    logo = models.ImageField("logo de l'événement", upload_to="evenements/logos/", blank=True, null=True)
    lieu = models.CharField("lieu", max_length=200, blank=True)
    ville = models.CharField("ville", max_length=100, blank=True)
    date_debut = models.DateField("date de début")
    heure_debut = models.TimeField("heure de début")
    date_fin = models.DateField("date de fin")
    date_limite_achat = models.DateTimeField("date limite d'achat")
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["date_debut", "heure_debut"]
        verbose_name = "événement"
        verbose_name_plural = "événements"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)[:150] or "evenement"
            slug, n = base, 2
            while Evenement.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        erreurs = {}
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            erreurs["date_fin"] = "La date de fin ne peut pas précéder la date de début."
        if self.date_limite_achat and self.date_debut:
            limite = self.date_limite_achat
            if timezone.is_naive(limite):
                limite = timezone.make_aware(limite)
            if limite.date() > self.date_fin:
                erreurs["date_limite_achat"] = "La date limite d'achat doit être avant la fin de l'événement."
        if erreurs:
            raise ValidationError(erreurs)

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.slug])

    @property
    def achats_ouverts(self):
        return self.statut == self.Statut.PUBLIE and timezone.now() <= self.date_limite_achat

    @property
    def est_passe(self):
        return self.date_fin < timezone.localdate()

    @property
    def tickets_vendus(self):
        from apps.tickets.models import Ticket

        return Ticket.objects.filter(
            type_ticket__evenement=self, commande__statut="paye"
        ).count()

    @property
    def revenus_bruts(self):
        from apps.tickets.models import Ticket

        return Ticket.objects.filter(
            type_ticket__evenement=self, commande__statut="paye"
        ).aggregate(t=Sum("prix_unitaire"))["t"] or Decimal("0")


class TypeTicket(models.Model):
    """Une ligne de tarification : catégorie, prix et stock (saisie dynamique)."""

    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="types_tickets")
    nom = models.CharField("type de ticket", max_length=80)
    prix = models.DecimalField("prix (FCFA)", max_digits=10, decimal_places=0)
    stock = models.PositiveIntegerField("stock disponible")
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "prix"]
        verbose_name = "type de ticket"

    def __str__(self):
        return f"{self.nom} · {self.prix} FCFA"

    @property
    def vendus(self):
        """Billets vendus OU réservés (commande payée ou en attente de paiement)."""
        from apps.tickets.models import Ticket

        return Ticket.objects.filter(
            type_ticket=self, commande__statut__in=["paye", "en_attente"]
        ).count()

    @property
    def restants(self):
        return max(self.stock - self.vendus, 0)

    @property
    def epuise(self):
        return self.restants == 0
