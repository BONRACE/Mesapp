"""Cartes de visite d'entreprise : payantes (100 FCFA), générées après paiement validé."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class CarteVisite(models.Model):
    class Theme(models.TextChoices):
        EMERAUDE = "emeraude", "Émeraude artisanal"
        PAPIER = "papier", "Papier kraft"
        MINIMAL = "minimal", "Minimal premium"
        ARCHE = "arche", "Arche de Ouidah"

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cartes_visite")
    theme = models.CharField(max_length=20, choices=Theme.choices, default=Theme.EMERAUDE)
    nom_entreprise = models.CharField("nom de l'entreprise", max_length=120)
    nom_contact = models.CharField("nom du contact", max_length=120)
    poste = models.CharField("poste", max_length=120, blank=True)
    telephone = models.CharField("téléphone", max_length=30)
    email = models.EmailField("e-mail")
    site_web = models.CharField("site web", max_length=120, blank=True)
    adresse = models.CharField("adresse", max_length=200, blank=True)
    slogan = models.CharField("slogan", max_length=140, blank=True)
    logo = models.ImageField("logo", upload_to="cartes/logos/", blank=True, null=True)
    paye = models.BooleanField(default=False)
    paiement = models.ForeignKey(
        "payments.Paiement", on_delete=models.PROTECT, null=True, blank=True, related_name="cartes"
    )
    genere_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "carte de visite"

    def __str__(self):
        return f"Carte · {self.nom_entreprise}"

    @property
    def generee(self):
        return self.paye and self.genere_le is not None
