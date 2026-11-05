from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    """Un abonnement organisateur. Créé en attente au lancement du paiement, activé par la transaction réussie."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    price = models.PositiveIntegerField("Prix payé (FCFA)")
    days = models.PositiveIntegerField("Durée (jours)")
    is_paid = models.BooleanField("Payé", default=False)
    method_key = models.CharField("Moyen de paiement (clé)", max_length=30, blank=True)
    method_label = models.CharField("Moyen de paiement", max_length=60, blank=True)
    reference = models.CharField("Référence", max_length=40, blank=True)
    provider_ref = models.CharField("Réf. opérateur", max_length=80, blank=True)
    starts_at = models.DateTimeField("Début", null=True, blank=True)
    ends_at = models.DateTimeField("Fin", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Abonnement {self.user} — {'actif jusqu’au ' + self.ends_at.strftime('%d/%m/%Y') if self.is_paid else 'en attente'}"
