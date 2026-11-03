from django.conf import settings
from django.db import models

from .catalog import BANK, CHANNELS, EMAIL, KIND_CHOICES


class PayoutMethod(models.Model):
    """Un canal de réception des fonds enregistré par un organisateur (Mobile Money, banque, PayPal…)."""

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_methods")
    kind = models.CharField("Canal", max_length=20, choices=KIND_CHOICES)
    label = models.CharField("Nom du moyen (facultatif)", max_length=60, blank=True)
    account_holder = models.CharField("Nom du titulaire", max_length=120)
    account_number = models.CharField("Numéro / compte", max_length=60)  # +229…, IBAN/RIB ou e-mail PayPal
    bank_name = models.CharField("Banque", max_length=100, blank=True)
    is_default = models.BooleanField("Moyen par défaut", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["organizer", "kind", "account_number"], name="uniq_payout_account")]

    def __str__(self):
        return f"{self.kind_label} — {self.display_account}"

    @property
    def kind_label(self):
        return CHANNELS.get(self.kind, {}).get("label", self.kind)

    @property
    def account_type(self):
        return CHANNELS.get(self.kind, {}).get("type")

    @property
    def display_account(self):
        """Compte partiellement masqué pour l'affichage et l'historique des retraits."""
        n = self.account_number
        if self.account_type == EMAIL and "@" in n:
            name, _, domain = n.partition("@")
            return f"{name[:1]}•••@{domain}"
        if len(n) <= 6:
            return n
        return n[:4] + "•" * (len(n) - 6) + n[-2:] if self.account_type != BANK else "•••• " + n[-4:]
