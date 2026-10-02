from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Event, TicketType
from .forms import EventForm, TicketTypeFormSet
from tickets.models import Ticket, calculer_solde
from tickets.payment_constants import moyens_paiement_pour
from tickets import fedapay_client
from tickets.fedapay_client import FedaPayError
from accounts.models import PlanAbonnement


def catalogue(request):
    aujourdhui = timezone.now().date()
    events = Event.objects.filter(statut=Event.Statut.PUBLIE, date_fin__gte=aujourdhui)
    return render(request, "events/catalogue.html", {"events": events})


def detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    is_own_event = request.user.is_authenticated and event.organisateur_id == request.user.id
    return render(request, "events/detail.html", {"event": event, "is_own_event": is_own_event})


@login_required
def acheter_billet(request, pk, type_id):
    """Étape 1 : choix du moyen de paiement, puis initiation d'une transaction FedaPay réelle.

    Le billet est créé tout de suite en statut EN_ATTENTE (le prix et la commission sont figés
    dès maintenant), et l'internaute est redirigé vers la page de paiement hébergée par FedaPay.
    Le billet n'est validé — et le stock décrémenté — qu'à la confirmation du paiement, reçue de
    façon fiable via le webhook `transaction.approved` (voir tickets.views_paiement).
    """
    event = get_object_or_404(Event, pk=pk)
    ticket_type = get_object_or_404(TicketType, pk=type_id, event=event)

    if event.organisateur_id == request.user.id:
        messages.error(request, "Tu ne peux pas acheter de billet pour ton propre événement.")
        return redirect("events:detail", pk=pk)

    if ticket_type.epuise:
        messages.error(request, "Ce type de billet est épuisé.")
        return redirect("events:detail", pk=pk)

    moyens = moyens_paiement_pour(request.user.pays)

    if request.method == "POST":
        moyen = request.POST.get("moyen_paiement")
        codes_valides = {code for code, _, _ in moyens}
        if moyen not in codes_valides:
            messages.error(request, "Merci de choisir un moyen de paiement valide.")
            return render(request, "events/paiement.html",
                           {"event": event, "ticket_type": ticket_type, "moyens": moyens})

        ticket = Ticket(spectateur=request.user, ticket_type=ticket_type)
        ticket.calculer_paiement(moyen)  # fige prix / commission tout de suite
        ticket.save()

        callback_url = request.build_absolute_uri(
            reverse("tickets:paiement_retour")) + f"?ticket={ticket.id}"
        try:
            transaction_id, checkout_url = fedapay_client.initier_paiement(
                description=f"Billet {ticket_type.nom} — {event.nom}",
                montant=ticket.montant_paye,
                devise="XOF",
                spectateur=request.user,
                callback_url=callback_url,
            )
        except FedaPayError as exc:
            ticket.delete()
            messages.error(request, f"Le paiement n'a pas pu être initié : {exc}")
            return render(request, "events/paiement.html",
                           {"event": event, "ticket_type": ticket_type, "moyens": moyens})

        ticket.fedapay_transaction_id = str(transaction_id)
        ticket.save(update_fields=["fedapay_transaction_id"])
        return redirect(checkout_url)

    context = {"event": event, "ticket_type": ticket_type, "moyens": moyens}
    return render(request, "events/paiement.html", context)


@login_required
def organisateur_dashboard(request):
    events = Event.objects.filter(organisateur=request.user)
    total_revenu = sum(e.revenu_total for e in events)
    total_revenu_net = sum(e.revenu_net_total for e in events)
    total_billets = sum(e.billets_vendus for e in events)
    context = {
        "events": events,
        "total_revenu": total_revenu,
        "total_revenu_net": total_revenu_net,
        "total_billets": total_billets,
        "total_events": events.count(),
        "events_publies": events.filter(statut=Event.Statut.PUBLIE).count(),
        "solde_disponible": calculer_solde(request.user),
        "plan": PlanAbonnement.pour(request.user),
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
