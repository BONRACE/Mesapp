from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from events.models import Event


def home(request):
    events = (
        Event.objects.filter(is_published=True, end_date__gte=timezone.localdate())
        .select_related("organizer").prefetch_related("ticket_types")[:6]
    )
    return render(request, "core/home.html", {"events": events})


@login_required
def dashboard(request):
    """Aiguille chaque utilisateur vers son espace."""
    if request.user.is_organisateur:
        return redirect("events:dashboard")
    return redirect("tickets:dashboard")


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_403(request, exception=None):
    return render(request, "403.html", {"message": str(exception) if exception else ""}, status=403)
