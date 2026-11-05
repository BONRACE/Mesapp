from django.http import JsonResponse
from django.shortcuts import render

from accounts.decorators import organizer_required
from events.models import Event

from .services import build_stats


def _selected_event(request):
    """Événement choisi via ?event=<id> (uniquement parmi ceux de l'organisateur), sinon None = tous."""
    raw = request.GET.get("event", "")
    if raw.isdigit():
        return Event.objects.filter(pk=int(raw), organizer=request.user).first()
    return None


@organizer_required
def dashboard(request):
    event = _selected_event(request)
    return render(request, "analytics/dashboard.html", {
        "events": request.user.events.order_by("-start_date"), "event": event,
    })


@organizer_required
def data(request):
    """JSON interrogé toutes les 10 s par la page pour le « temps réel »."""
    resp = JsonResponse(build_stats(request.user, _selected_event(request)))
    resp["Cache-Control"] = "no-store"
    return resp
