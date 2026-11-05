import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from accounts.decorators import organizer_required
from events.models import Event

from .models import ScanLog
from .services import check_in, event_stats


@organizer_required
def index(request):
    """Liste des événements de l'organisateur avec l'avancement du contrôle d'entrée."""
    events = [(e, event_stats(e)) for e in request.user.events.filter(is_published=True).order_by("-start_date")]
    return render(request, "scanner/index.html", {"events": events})


@organizer_required
def scan_page(request, event_id):
    event = get_object_or_404(Event, pk=event_id, organizer=request.user)
    recent = event.scans.select_related("ticket__order__buyer")[:10]
    return render(request, "scanner/scan.html", {"event": event, "stats": event_stats(event), "recent": recent})


@organizer_required
@require_POST
def scan_api(request, event_id):
    """POST JSON {"code": "<texte du QR>", "source": "camera|manual"} -> résultat du contrôle."""
    event = get_object_or_404(Event, pk=event_id, organizer=request.user)
    try:
        payload = json.loads(request.body.decode() or "{}")
        code = str(payload.get("code", ""))
    except (ValueError, AttributeError):
        return JsonResponse({"detail": "Requête invalide."}, status=400)
    source = payload.get("source") if payload.get("source") in ScanLog.Source.values else ScanLog.Source.CAMERA
    return JsonResponse(check_in(user=request.user, event=event, code=code, source=source))
