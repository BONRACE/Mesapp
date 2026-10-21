from django.conf import settings
from django.db import models
from django.urls import reverse


class BusinessCard(models.Model):
    """Carte de visite d'entreprise. La génération (PDF/PNG) exige un paiement validé."""

    class Theme(models.TextChoices):
        EMERAUDE = "emeraude", "Émeraude"
        MINUIT = "minuit", "Minuit"
        KRAFT = "kraft", "Kraft artisanal"
        PAGNE = "pagne", "Pagne"
        IVOIRE = "ivoire", "Ivoire & or"
        SAUGE = "sauge", "Sauge"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_cards")
    theme = models.CharField("modèle", max_length=20, choices=Theme.choices, default=Theme.EMERAUDE)
    company_name = models.CharField("nom de l'entreprise", max_length=80)
    contact_name = models.CharField("nom du contact", max_length=80)
    job_title = models.CharField("poste", max_length=80, blank=True)
    phone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    website = models.CharField("site web", max_length=120, blank=True)
    address = models.CharField("adresse", max_length=160, blank=True)
    tagline = models.CharField("slogan", max_length=90, blank=True)
    logo = models.ImageField("logo", upload_to="cartes/logos/", blank=True)
    is_paid = models.BooleanField("payée", default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company_name} ({self.get_theme_display()})"

    def get_absolute_url(self):
        return reverse("cards:detail", args=[self.pk])
