from django.core.management.base import BaseCommand

from marketplace.services import expire_stale_orders


class Command(BaseCommand):
    help = "Expire les commandes non payées et restitue le stock (à lancer toutes les 5 min : cron / boucle du conteneur)."

    def handle(self, *args, **opts):
        self.stdout.write(f"{expire_stale_orders()} commande(s) expirée(s).")
