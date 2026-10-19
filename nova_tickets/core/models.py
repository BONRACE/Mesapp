import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


def new_card_reference():
    return "CV-" + uuid.uuid4().hex[:8].upper()


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
    TEMPLATES = [("atelier", "Atelier"), ("epure", "Épuré"), ("prestige", "Prestige"), ("wax", "Wax"),
                 ("aurore", "Aurore")]
    template = models.CharField("Modèle", max_length=12, choices=TEMPLATES, default="atelier")
    social = models.CharField("Réseau social", max_length=60, blank=True)
    # Renseignée au paiement des 100 FCFA : tant qu'elle est vide, seul un aperçu filigrané est disponible.
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.company_name} – {self.contact_name}"

    def get_absolute_url(self):
        return reverse("core:card_detail", args=[self.pk])

    @property
    def is_paid(self):
        return self.paid_at is not None


class CardPayment(models.Model):
    """Paiement (simulé) de la génération d'une carte de visite."""

    PENDING, PAID, FAILED = "pending", "paid", "failed"
    STATUSES = [(PENDING, "En attente"), (PAID, "Payé"), (FAILED, "Échoué")]

    card = models.ForeignKey(BusinessCard, on_delete=models.CASCADE, related_name="payments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="card_payments")
    reference = models.CharField(max_length=20, unique=True, default=new_card_reference)
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    method = models.CharField(max_length=60)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference
