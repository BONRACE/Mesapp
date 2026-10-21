from django.apps import AppConfig


class CardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cards"

    def ready(self):
        from . import receivers  # noqa: F401  (branche le signal de fin de paiement)
