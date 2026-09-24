from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Event, TicketType
from .forms import EventForm, TicketTypeFormSet
from tickets.models import Ticket


def catalogue(request):
    aujourdhui = timezone.now().date()
    events = Event.objects.filter(statut=Event.Statut.PUBLIE, date_fin__gte=aujourdhui)
    return render(request, "events/catalogue.html", {"events": events})


def detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    return render(request, "events/detail.html", {"event": event})


@login_required
def acheter_billet(request, pk, type_id):
    event = get_object_or_404(Event, pk=pk)
    ticket_type = get_object_or_404(TicketType, pk=type_id, event=event)
    if ticket_type.epuise:
        messages.error(request, "Ce type de billet est épuisé.")
        return redirect("events:detail", pk=pk)

    ticket = Ticket.objects.create(spectateur=request.user, ticket_type=ticket_type)
    ticket_type.quantite_vendue += 1
    ticket_type.save()
    messages.success(request, "Billet réservé ! Retrouve-le dans ton tableau de bord.")
    return redirect("tickets:detail", pk=ticket.id)


@login_required
def organisateur_dashboard(request):
    events = Event.objects.filter(organisateur=request.user)
    total_revenu = sum(e.revenu_total for e in events)
    total_billets = sum(e.billets_vendus for e in events)
    context = {
        "events": events,
        "total_revenu": total_revenu,
        "total_billets": total_billets,
        "total_events": events.count(),
        "events_publies": events.filter(statut=Event.Statut.PUBLIE).count(),
    }
    return render(request, "events/organisateur_dashboard.html", context)


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        formset = TicketTypeFormSet(request.POST, prefix="tickettype")
        if form.is_valid() and formset.is_valid():
            event = form.save(commit=False)
            event.organisateur = request.user
            event.save()
            formset.instance = event
            formset.save()
            messages.success(request, f"« {event.nom} » a été publié avec succès 🎉")
            return redirect("events:organisateur_dashboard")
    else:
        form = EventForm()
        formset = TicketTypeFormSet(prefix="tickettype")
    return render(request, "events/event_form.html", {"form": form, "formset": formset})


@login_required
def event_manage(request, pk):
    event = get_object_or_404(Event, pk=pk, organisateur=request.user)
    tickets = Ticket.objects.filter(ticket_type__event=event).select_related("spectateur", "ticket_type")
    return render(request, "events/event_manage.html", {"event": event, "tickets": tickets})
