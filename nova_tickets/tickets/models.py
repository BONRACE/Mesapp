import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Statut(models.TextChoices):
        VALIDE = "valide", "Valide"
        UTILISE = "utilise", "Utilisé"
        ANNULE = "annule", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spectateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="billets")
    ticket_type = models.ForeignKey("events.TicketType", on_delete=models.CASCADE,
                                     related_name="billets")
    code = models.CharField(max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.VALIDE)
    achete_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-achete_le"]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"NT-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.spectateur.nom_complet}"

    @property
    def event(self):
        return self.ticket_type.event

    @property
    def est_a_venir(self):
        return self.event.date_fin >= timezone.now().date()

    @property
    def qr_payload(self):
        return f"NOVA-TICKET|{self.id}|{self.code}"

    @property
    def statut_affiche(self):
        if self.statut == self.Statut.ANNULE:
            return "Annulé"
        if not self.est_a_venir:
            return "Utilisé"
        return "Confirmé"

    @property
    def statut_badge_css(self):
        if self.statut == self.Statut.ANNULE:
            return "bg-red-100 text-red-600"
        if not self.est_a_venir:
            return "bg-emerald-100 text-emerald-600"
        return "bg-blue-100 text-blue-600"
