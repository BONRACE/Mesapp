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


def terms(request):
    """Conditions Générales d'Utilisation et Politique d'utilisation (chiffres lus dans les réglages)."""
    from django.conf import settings
    return render(request, "core/terms.html", {
        "updated": "2 novembre 2026", "company": settings.LEGAL_COMPANY, "min_withdrawal": settings.MIN_WITHDRAWAL,
        "card_price": settings.BUSINESS_CARD_PRICE, "sub_price": settings.SUBSCRIPTION_PRICE, "sub_days": settings.SUBSCRIPTION_DAYS,
    })


def verify(request, reference):
    """Page de contrôle ouverte en scannant le QR code d'un billet (appareil photo natif du téléphone)."""
    from scanner.models import ScanLog
    from scanner.services import check_in

    from django.utils.crypto import constant_time_compare

    from orders.services import ticket_signature

    ticket = Ticket.objects.select_related("order__event__organizer", "order__buyer", "order__ticket_type").filter(reference=reference).first()
    is_event_organizer = bool(ticket and request.user.is_authenticated and ticket.order.event.organizer_id == request.user.id)
    signed = bool(ticket) and constant_time_compare(request.GET.get("s", ""), ticket_signature(reference))
    if not ticket or not (signed or is_event_organizer):
        # Même réponse pour « référence inconnue » et « lien non signé » : impossible de deviner des références.
        return render(request, "core/verify_unknown.html", status=404)
    can_validate = is_event_organizer
    if request.method == "POST":
        if can_validate:
            result = check_in(user=request.user, event=ticket.order.event, code=reference, source=ScanLog.Source.LINK)
            (messages.success if result["result"] == "valid" else messages.error)(request, result["message"])
        return redirect(request.get_full_path())
    return render(request, "core/verify.html", {"ticket": ticket, "can_validate": can_validate, "show_holder": is_event_organizer})
