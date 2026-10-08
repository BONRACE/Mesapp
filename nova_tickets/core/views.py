from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.countries import withdrawal_methods_for
from events.models import Event
from orders.models import Order, Ticket, Withdrawal


def home(request):
    today = timezone.localdate()
    q = request.GET.get("q", "").strip()
    events = Event.objects.filter(status=Event.PUBLISHED, end_date__gte=today).prefetch_related("ticket_types")
    if q:
        events = events.filter(Q(name__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q))
    return render(request, "core/home.html", {"events": events, "q": q})


@login_required
def dashboard_redirect(request):
    return redirect("core:organizer_dashboard" if request.user.is_organisateur else "core:spectateur_dashboard")


@login_required
def spectateur_dashboard(request):
    if request.user.is_organisateur:
        return redirect("core:organizer_dashboard")
    today = timezone.localdate()
    orders = (Order.objects.filter(user=request.user, status=Order.PAID)
              .select_related("event", "ticket_type").prefetch_related("tickets"))
    upcoming = [o for o in orders if o.event.end_date >= today]
    past = [o for o in orders if o.event.end_date < today]
    return render(request, "dashboard/spectateur.html", {
        "upcoming": upcoming, "past": past,
        "tickets_count": sum(o.quantity for o in orders),
        "spent": sum((o.total for o in orders), Decimal("0")),
    })


@login_required
def organizer_dashboard(request):
    if not request.user.is_organisateur:
        raise PermissionDenied
    user = request.user
    events = user.events.prefetch_related("ticket_types")
    paid = Order.objects.filter(event__organizer=user, status=Order.PAID)
    recent = paid.select_related("event", "user", "ticket_type")[:8]
    return render(request, "dashboard/organizer.html", {
        "events": events,
        "recent": recent,
        "tickets_sold": paid.aggregate(t=Sum("quantity"))["t"] or 0,
        "withdrawals": user.withdrawals.all()[:10],
        "withdraw_methods": withdrawal_methods_for(user.country),
    })


@login_required
@require_POST
def withdraw(request):
    user = request.user
    if not user.is_organisateur:
        raise PermissionDenied
    method = request.POST.get("method", "")
    phone = request.POST.get("phone", "").strip()
    try:
        amount = Decimal(request.POST.get("amount", "0"))
    except Exception:
        amount = Decimal("0")
    if method not in withdrawal_methods_for(user.country):
        messages.error(request, "Moyen de retrait non disponible dans votre pays.")
    elif amount < 500:
        messages.error(request, "Montant minimum de retrait : 500 FCFA.")
    elif amount > user.available_balance:
        messages.error(request, "Montant supérieur à votre solde disponible.")
    elif len("".join(c for c in phone if c.isdigit())) < 6:
        messages.error(request, "Entrez un numéro de réception valide.")
    else:
        Withdrawal.objects.create(organizer=user, amount=amount, method=method, phone=phone)
        messages.success(request, "Demande de retrait enregistrée. Le versement est en cours.")
    return redirect("core:organizer_dashboard")
