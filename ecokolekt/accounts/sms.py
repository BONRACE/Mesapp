"""Envoi de SMS, derrière une interface commune pour changer de fournisseur sans toucher au reste."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ConsoleSMS:
    """Développement : affiche le message dans les logs."""

    def send(self, phone_number, message):
        logger.warning("[SMS -> %s] %s", phone_number, message)


class HttpSMS:
    """Exemple de passerelle HTTP. Adapter l'URL, les en-têtes et le payload au fournisseur retenu."""

    endpoint = "https://sms.example.com/api/send"

    def send(self, phone_number, message):
        response = requests.post(
            self.endpoint,
            json={"to": phone_number, "text": message},
            timeout=10,
        )
        response.raise_for_status()


def get_sms_backend():
    if settings.SMS_BACKEND == "http":
        return HttpSMS()
    return ConsoleSMS()
