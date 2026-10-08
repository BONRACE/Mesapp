from django.conf import settings
from django.contrib import messages
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import organizer_required
from core.payments import payout_methods_for_country
from orders.models import Order, Withdrawal
from orders.services import PurchaseError, organizer_balance, request_withdrawal

from .forms import EventForm, TicketFormSet
from .models import Event


def detail(request, pk):
    event = get_object_or_404(Event.objects.select_related("organizer"), pk=pk)
    is_owner = request.user.is_authenticated and event.organizer_id == request.user.id
    if not event.is_published and not is_owner:
        raise Http404
    return render(request, "events/detail.html", {
        "event": event,
        "ticket_types": event.ticket_types.all(),
        "is_owner": is_owner,
    })


@organizer_required
def orga_dashboard(request):
    user = request.user
    paid = Order.objects.filter(event__organizer=user, status=Order.Status.PAID)
    agg = paid.aggregate(gross=Sum("total"), commission=Sum("commission"), net=Sum("organizer_amount"), tickets=Sum("quantity"))
    events = list(user.events.all())
    recent = paid.select_related("event", "ticket_type", "buyer").order_by("-paid_at")[:8]
    return render(request, "events/orga_dashboard.html", {
        "gross": agg["gross"] or 0,
        "commission": agg["commission"] or 0,
        "net": agg["net"] or 0,
        "tickets": agg["tickets"] or 0,
        "balance": organizer_balance(user),
        "events": events,
        "recent": recent,
        "today": timezone.localdate(),
    })


def _save_event(request, event=None):
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    formset = TicketFormSet(request.POST or None, instance=event, prefix="tt")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        obj = form.save(commit=False)
        obj.organizer = request.user
        obj.save()
        formset.instance = obj
        formset.save()
        return obj, form, formset
    return None, form, formset


@organizer_required
def event_create(request):
    obj, form, formset = _save_event(request)
    if obj:
        messages.success(request, "Événement créé. Publiez-le quand vous êtes prêt.")
        return redirect("events:orga_dashboard")
    return render(request, "events/event_form.html", {"form": form, "formset": formset, "title": "Créer un événement", "event": None})


@organizer_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    obj, form, formset = _save_event(request, event)
    if obj:
        messages.success(request, "Événement mis à jour.")
        return redirect("events:orga_dashboard")
    return render(request, "events/event_form.html", {"form": form, "formset": formset, "title": "Modifier l'événement", "event": event})


@organizer_required
@require_POST
def event_toggle(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    if not event.is_published and not event.ticket_types.exists():
        messages.error(request, "Ajoutez au moins un type de ticket avant de publier.")
    else:
        event.is_published = not event.is_published
        event.save(update_fields=["is_published"])
        messages.success(request, "Événement publié." if event.is_published else "Événement dépublié.")
    return redirect("events:orga_dashboard")


@organizer_required
def withdraw(request):
    user = request.user
    methods = payout_methods_for_country(user.country)
    balance = organizer_balance(user)
    if request.method == "POST":
        try:
            amount = int(request.POST.get("amount", "0"))
        except ValueError:
            amount = 0
        try:
            wd = request_withdrawal(user, amount, request.POST.get("method", ""), request.POST.get("phone", user.phone))
        except PurchaseError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Retrait de {wd.amount} {settings.CURRENCY} envoyé vers {wd.method_label} (simulation).")
            return redirect("events:withdraw")
    return render(request, "events/withdraw.html", {
        "balance": balance,
        "methods": methods,
        "history": Withdrawal.objects.filter(organizer=user),
        "min_withdrawal": settings.MIN_WITHDRAWAL,
    })
