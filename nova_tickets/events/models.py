import uuid
from django.conf import settings
from django.db import models
from django.urls import reverse


class Event(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        PUBLIE = "publie", "Publié"
        TERMINE = "termine", "Terminé"
        ANNULE = "annule", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="evenements")
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lieu = models.CharField(max_length=200, blank=True)
    ville = models.CharField(max_length=120, blank=True)

    visuel = models.ImageField(upload_to="evenements/visuels/", blank=True, null=True)
    logo = models.ImageField(upload_to="evenements/logos/", blank=True, null=True)

    date_debut = models.DateField()
    date_fin = models.DateField()
    heure_debut = models.TimeField()
    date_limite_achat = models.DateField()

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PUBLIE)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_debut"]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.id])

    @property
    def logo_effectif(self):
        return self.logo or self.organisateur.logo_organisateur

    @property
    def billets_vendus(self):
        return sum(tt.quantite_vendue for tt in self.types_billets.all())

    @property
    def stock_total(self):
        return sum(tt.quantite_disponible for tt in self.types_billets.all())

    @property
    def revenu_total(self):
        return sum(tt.quantite_vendue * tt.prix for tt in self.types_billets.all())

    @property
    def taux_remplissage(self):
        total = self.stock_total
        return round((self.billets_vendus / total) * 100) if total else 0


class TicketType(models.Model):
    """Catégorie de billet : Standard, VIP, Early Bird, etc. avec prix et stock."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="types_billets")
    nom = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=0)  # FCFA, pas de décimales
    quantite_disponible = models.PositiveIntegerField(default=0)
    quantite_vendue = models.PositiveIntegerField(default=0)
    couleur_badge = models.CharField(max_length=20, default="violet")  # violet / or / cyan

    class Meta:
        ordering = ["prix"]

    def __str__(self):
        return f"{self.nom} — {self.event.nom}"

    @property
    def restant(self):
        return max(self.quantite_disponible - self.quantite_vendue, 0)

    @property
    def epuise(self):
        return self.restant <= 0
