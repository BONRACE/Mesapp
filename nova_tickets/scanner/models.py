from django.conf import settings
from django.db import models


class ScanLog(models.Model):
    """Journal de chaque contrôle de billet (valide ou non) : alimente l'affluence des analytiques."""

    class Result(models.TextChoices):
        VALID = "valid", "Entrée validée"
        DUPLICATE = "duplicate", "Déjà utilisé"
        WRONG_EVENT = "wrong_event", "Autre événement"
        INVALID = "invalid", "Billet invalide"

    class Source(models.TextChoices):
        CAMERA = "camera", "Caméra"
        MANUAL = "manual", "Saisie manuelle"
        LINK = "link", "Lien du QR code"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="scans")
    ticket = models.ForeignKey("orders.Ticket", null=True, blank=True, on_delete=models.SET_NULL, related_name="scans")
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="scans")
    code = models.CharField(max_length=200, blank=True)
    result = models.CharField(max_length=12, choices=Result.choices)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.CAMERA)
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [models.Index(fields=["event", "result", "scanned_at"])]

    def __str__(self):
        return f"{self.get_result_display()} — {self.code}"
