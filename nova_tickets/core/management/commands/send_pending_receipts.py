"""Relance les reçus qui ne sont pas partis (serveur e-mail indisponible, configuration corrigée plus tard…).

    python manage.py send_pending_receipts            # commandes payées depuis 3 jours
    python manage.py send_pending_receipts --days 10

À lancer à la main ou via une tâche planifiée (cron / Planificateur de tâches Windows), par ex. toutes les 10 min.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders import services
from orders.models import Order


class Command(BaseCommand):
    help = "Renvoie les reçus des commandes payées dont l'e-mail n'est jamais parti."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3, help="Ancienneté maximale des commandes (défaut : 3 jours)")

    def handle(self, *args, **opts):
        if services.email_is_console():
            self.stderr.write(self.style.ERROR(
                "Mode console : aucun e-mail ne peut partir. Renseignez EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans .env."))
            return
        since = timezone.now() - timedelta(days=opts["days"])
        pending = (Order.objects.filter(status=Order.PAID, receipt_sent_at__isnull=True, created_at__gte=since)
                   .exclude(user__email="").select_related("user", "event", "ticket_type"))
        sent = failed = 0
        for order in pending:
            if services.send_receipt(order):
                sent += 1
                self.stdout.write(f"✔ {order.reference} → {order.user.email}")
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"✘ {order.reference} → {order.user.email} (voir les erreurs ci-dessus)"))
        self.stdout.write(self.style.SUCCESS(f"Terminé : {sent} envoyé(s), {failed} échec(s)."))
