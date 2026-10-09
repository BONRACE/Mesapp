from django.conf import settings
from django.db import models
from django.urls import reverse


class BusinessCard(models.Model):
    """Carte de visite d'une entreprise (rendue en PNG recto/verso, PDF et vCard)."""

    COLORS = [
        ("#059669", "Vert"),
        ("#1d4e89", "Bleu"),
        ("#ea580c", "Orange"),
        ("#7c3aed", "Violet"),
        ("#be123c", "Rouge"),
        ("#0f172a", "Noir"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cards")
    company_name = models.CharField("Nom de l'entreprise", max_length=80)
    tagline = models.CharField("Slogan / activité", max_length=100, blank=True)
    contact_name = models.CharField("Nom du contact", max_length=80)
    job_title = models.CharField("Fonction", max_length=80, blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    website = models.CharField("Site web", max_length=120, blank=True)
    address = models.CharField("Adresse", max_length=160, blank=True)
    logo = models.ImageField("Logo", upload_to="cards/", blank=True, null=True)
    color = models.CharField("Couleur", max_length=7, choices=COLORS, default="#059669")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.company_name} – {self.contact_name}"

    def get_absolute_url(self):
        return reverse("core:card_detail", args=[self.pk])
