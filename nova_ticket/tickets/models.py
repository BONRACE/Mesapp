import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente de paiement"
        VALIDE = "valide", "Valide"
        UTILISE = "utilise", "Utilisé"
        ANNULE = "annule", "Annulé"

    MOYEN_PAIEMENT_CHOICES = [
        ("mtn_momo", "MTN Mobile Money"),
        ("moov_money", "Moov Money"),
        ("orange_money", "Orange Money"),
        ("carte", "Carte bancaire"),
        ("paypal", "PayPal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spectateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="billets")
    ticket_type = models.ForeignKey("events.TicketType", on_delete=models.CASCADE,
                                     related_name="billets")
    code = models.CharField(max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    achete_le = models.DateTimeField(auto_now_add=True)

    # Paiement & commission plateforme
    moyen_paiement = models.CharField(max_length=20, choices=MOYEN_PAIEMENT_CHOICES, blank=True)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    commission_pourcentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_montant = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    montant_net_organisateur = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    # Référence FedaPay — permet au webhook de retrouver ce billet à la confirmation du paiement
    fedapay_transaction_id = models.CharField(max_length=40, blank=True, null=True,
                                               unique=True, db_index=True)

    class Meta:
        ordering = ["-achete_le"]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"NT-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.spectateur.nom_complet}"

    def calculer_paiement(self, moyen_paiement):
        """Fixe le montant payé et répartit la commission plateforme / montant net organisateur,
        selon le plan (FREE ou PRO) de l'organisateur de l'événement."""
        from accounts.models import PlanAbonnement

        plan = PlanAbonnement.pour(self.event.organisateur)
        pourcentage = Decimal(str(plan.commission_pourcentage()))
        prix = Decimal(self.ticket_type.prix)
        commission = (prix * pourcentage / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        self.moyen_paiement = moyen_paiement
        self.montant_paye = prix
        self.commission_pourcentage = pourcentage
        self.commission_montant = commission
        self.montant_net_organisateur = prix - commission

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
        if self.statut == self.Statut.EN_ATTENTE:
            return "En attente de paiement"
        if self.statut == self.Statut.ANNULE:
            return "Annulé"
        if not self.est_a_venir:
            return "Utilisé"
        return "Confirmé"

    @property
    def statut_badge_css(self):
        if self.statut == self.Statut.EN_ATTENTE:
            return "bg-amber-100 text-amber-700"
        if self.statut == self.Statut.ANNULE:
            return "bg-red-100 text-red-600"
        if not self.est_a_venir:
            return "bg-emerald-100 text-emerald-600"
        return "bg-blue-100 text-blue-600"


class Retrait(models.Model):
    """Demande de retrait des fonds nets accumulés par un organisateur."""

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        REUSSI = "reussi", "Réussi"
        ECHOUE = "echoue", "Échoué"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="retraits")
    montant = models.DecimalField(max_digits=10, decimal_places=0)
    moyen_paiement = models.CharField(max_length=20, choices=Ticket.MOYEN_PAIEMENT_CHOICES)
    destination = models.CharField(max_length=100, blank=True,
                                    help_text="Numéro Mobile Money ou identifiant du moyen choisi")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.REUSSI)
    demande_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-demande_le"]

    def __str__(self):
        return f"Retrait {self.montant} FCFA — {self.organisateur.nom_complet}"


def calculer_solde(organisateur):
    """Solde net disponible au retrait pour un organisateur (revenus nets - retraits réussis).

    Seuls les billets effectivement payés (VALIDE ou UTILISE) comptent — un billet encore
    EN_ATTENTE de confirmation FedaPay, ou ANNULE, n'est pas un revenu acquis.
    """
    from django.db.models import Sum

    total_net = Ticket.objects.filter(
        ticket_type__event__organisateur=organisateur,
        statut__in=[Ticket.Statut.VALIDE, Ticket.Statut.UTILISE],
    ).aggregate(s=Sum("montant_net_organisateur"))["s"] or 0

    total_retire = Retrait.objects.filter(
        organisateur=organisateur, statut=Retrait.Statut.REUSSI
    ).aggregate(s=Sum("montant"))["s"] or 0

    return total_net - total_retire
