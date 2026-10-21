from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.permissions import organisateur_required

from .forms import EventForm, TicketTypeFormSet
from .models import Event


def event_list(request):
    qs = Event.objects.filter(is_published=True, end_date__gte=timezone.localdate()).prefetch_related("ticket_types")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(venue__icontains=q))
    return render(request, "events/list.html", {"events": qs, "q": q})


def event_detail(request, slug):
    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), slug=slug)
    is_owner = request.user.is_authenticated and event.organizer_id == request.user.id
    if not event.is_published and not is_owner:
        # Un événement non publié reste invisible pour tous sauf son organisateur.
        return render(request, "404.html", status=404)
    return render(request, "events/detail.html", {"event": event, "is_owner": is_owner})


# --- Espace organisateur ---------------------------------------------------

@organisateur_required
def dashboard(request):
    from payments.models import Withdrawal
    from payments.services import organizer_balance
    from tickets.models import Order

    user = request.user
    paid = Order.objects.filter(event__organizer=user, status=Order.Status.PAID)
    totals = paid.aggregate(gross=Sum("total"), commission=Sum("commission"), qty=Sum("quantity"))
    gross, commission = totals["gross"] or 0, totals["commission"] or 0
    events = user.events.prefetch_related("ticket_types")
    stats = {
        "orders": paid.count(),
        "tickets": totals["qty"] or 0,
        "gross": gross,
        "commission": commission,
        "net": gross - commission,
        "active_events": sum(1 for e in events if e.is_published and not e.is_past),
    }
    return render(request, "events/dashboard.html", {
        "stats": stats,
        "events": events,
        "balance": organizer_balance(user),
        "recent_orders": paid.select_related("event", "buyer", "ticket_type")[:8],
        "recent_withdrawals": Withdrawal.objects.filter(organizer=user)[:3],
    })


def _save_event_and_types(request, event, form_kwargs):
    form = EventForm(request.POST or None, request.FILES or None, **form_kwargs)
    formset = TicketTypeFormSet(request.POST or None, instance=event, prefix="types")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.organizer = request.user
            obj.save()
            formset.instance = obj
            formset.save()
        return obj, form, formset
    return None, form, formset


@organisateur_required
def event_create(request):
    obj, form, formset = _save_event_and_types(request, Event(), {})
    if obj:
        messages.success(request, "Événement enregistré. Il n'est pas encore visible : cliquez sur « Publier » quand vous êtes prêt.")
        return redirect("events:manage", slug=obj.slug)
    return render(request, "events/form.html", {"form": form, "formset": formset, "editing": False})


@organisateur_required
def event_edit(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    obj, form, formset = _save_event_and_types(request, event, {"instance": event})
    if obj:
        messages.success(request, "Événement mis à jour.")
        return redirect("events:manage", slug=obj.slug)
    return render(request, "events/form.html", {"form": form, "formset": formset, "editing": True, "event": event})


@organisateur_required
def event_manage(request, slug):
    from tickets.models import Order, Ticket

    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), slug=slug, organizer=request.user)
    orders = Order.objects.filter(event=event, status=Order.Status.PAID).select_related("buyer", "ticket_type")
    totals = orders.aggregate(gross=Sum("total"), commission=Sum("commission"))
    return render(request, "events/manage.html", {
        "event": event,
        "orders": orders[:50],
        "gross": totals["gross"] or 0,
        "net": (totals["gross"] or 0) - (totals["commission"] or 0),
        "tickets_count": Ticket.objects.filter(order__event=event, order__status=Order.Status.PAID).count(),
    })


@organisateur_required
def event_toggle_publish(request, slug):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    if not event.is_published and not event.ticket_types.exists():
        messages.error(request, "Ajoutez au moins un type de ticket avant de publier.")
    else:
        event.is_published = not event.is_published
        event.save(update_fields=["is_published"])
        messages.success(request, "Événement publié !" if event.is_published else "Événement dépublié.")
    return redirect(request.POST.get("next") or "events:dashboard")


@organisateur_required
def event_delete(request, slug):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    if event.orders.exists():
        messages.error(request, "Cet événement a des commandes : dépubliez-le plutôt que de le supprimer.")
    else:
        event.delete()
        messages.success(request, "Événement supprimé.")
    return redirect("events:dashboard")
