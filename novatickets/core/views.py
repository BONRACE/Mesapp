from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from events.models import Event
from orders.models import Ticket


def home(request):
    today = timezone.localdate()
    qs = Event.objects.filter(is_published=True, end_date__gte=today).select_related("organizer").prefetch_related("ticket_types")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q) | Q(organizer__org_name__icontains=q))
    return render(request, "core/home.html", {"events": qs, "q": q})


def verify(request, reference):
    """Page de contrôle ouverte en scannant le QR code d'un billet."""
    ticket = get_object_or_404(Ticket.objects.select_related("order__event__organizer", "order__buyer", "order__ticket_type"), reference=reference)
    can_validate = request.user.is_authenticated and ticket.order.event.organizer_id == request.user.id
    if request.method == "POST":
        if not can_validate:
            return redirect("core:verify", reference=reference)
        if ticket.is_used:
            messages.error(request, "Ce billet a déjà été utilisé.")
        else:
            ticket.used_at = timezone.now()
            ticket.save(update_fields=["used_at"])
            messages.success(request, "Entrée validée.")
        return redirect("core:verify", reference=reference)
    return render(request, "core/verify.html", {"ticket": ticket, "can_validate": can_validate})
