"""Modèle de transaction Mobile Money (MTN MoMo / Moov Money)."""
import uuid

from django.db import models


class Transaction(models.Model):
    """Une tentative de paiement Mobile Money.

    Cycle de vie : PENDING (créée, push envoyé) -> SUCCESS ou FAILED (décidé par le webhook).
    Une transaction terminée (SUCCESS / FAILED) ne change plus jamais d'état.
    """

    class Provider(models.TextChoices):
        MTN = "MTN", "MTN MoMo"
        MOOV = "Moov", "Moov Money"
        FEDAPAY = "FEDA", "FedaPay"          # paiement via la page FedaPay (Mobile Money, carte…)

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SUCCESS = "SUCCESS", "Réussi"
        FAILED = "FAILED", "Échoué"

    # Clé primaire UUID : non devinable, donc utilisable dans l'URL de la page de statut / reçu.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_email = models.EmailField("E-mail du payeur")
    phone_number = models.CharField("Numéro Mobile Money", max_length=15)  # format 229XXXXXXXXXX
    amount = models.DecimalField("Montant (FCFA)", max_digits=12, decimal_places=2)
    provider = models.CharField("Opérateur", max_length=4, choices=Provider.choices)
    status = models.CharField("Statut", max_length=7, choices=Status.choices, default=Status.PENDING, db_index=True)
    reference = models.CharField("Référence marchand", max_length=40, unique=True)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    # Champs complémentaires utiles à l'exploitation (non obligatoires dans le cahier des charges)
    gateway_reference = models.CharField("Référence passerelle", max_length=80, blank=True)
    failure_reason = models.CharField("Motif d'échec", max_length=200, blank=True)
    paid_at = models.DateTimeField("Payée le", null=True, blank=True)
    checkout_url = models.URLField("Page de paiement (FedaPay)", max_length=400, blank=True)

    # Ce que la transaction paie (au plus un des deux ; aucun = paiement autonome / démo).
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")
    business_card = models.ForeignKey("cards.BusinessCard", null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")

    subscription = models.ForeignKey("subscriptions.Subscription", null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.amount} FCFA — {self.get_status_display()}"

    @property
    def purpose(self):
        return "order" if self.order_id else "card" if self.business_card_id else "subscription" if self.subscription_id else "standalone"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_success(self):
        return self.status == self.Status.SUCCESS

    @property
    def masked_phone(self):
        """Numéro partiellement masqué pour l'affichage (ex. 229•••••••01)."""
        p = self.phone_number
        return p[:3] + "•" * max(len(p) - 5, 0) + p[-2:]
