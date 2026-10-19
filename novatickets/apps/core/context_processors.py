import json

from django.conf import settings

from apps.core.countries import indicatifs_json


def novatickets(request):
    """Variables globales : identité, réglages métier, données des sélecteurs de pays."""
    return {
        "NT": {**settings.NOVATICKETS, "PRIX_CARTE_VISITE": settings.NOVATICKETS["PRIX_CARTE_VISITE"]},
        "indicatifs_json": json.dumps(indicatifs_json()),
    }
