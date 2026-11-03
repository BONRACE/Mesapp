from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.payments import find_method, methods_for_country
from events.models import TicketType

from .models import Order, Ticket
from .services import (
    PurchaseError, create_order, order_receipt_pdf, pay_order, qr_png, start_mobile_money, ticket_pdf, tickets_pdf, verify_url,
)


@login_required
@require_POST
def checkout(request, pk):
    ticket_type = get_object_or_404(TicketType.objects.select_related("event"), pk=request.POST.get("ticket_type") or 0, event_id=pk)
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except ValueError:
        quantity = 0
    try:
        order = create_order(request.user, ticket_type, quantity)
    except PurchaseError as exc:
        messages.error(request, str(exc))
        return redirect("events:detail", pk=pk)
    return redirect("orders:pay", reference=order.reference)


def _pay_context(request, order, methods):
    """Contexte de la page de paiement. Après une erreur de saisie, on garde le moyen choisi et le numéro tapé
    (sinon le premier moyen de la liste serait re-sélectionné et le client pourrait payer avec le mauvais opérateur)."""
    return {"order": order, "methods": methods,
            "selected": request.POST.get("method", ""), "phone": request.POST.get("phone", request.user.phone)}


@login_required
def pay(request, reference):
    order = get_object_or_404(Order.objects.select_related("event", "ticket_type"), reference=reference, buyer=request.user)
    if order.status == Order.Status.PAID:
        return redirect("orders:confirmation", reference=order.reference)
    methods = methods_for_country(request.user.country)
    if request.method == "POST":
        method = find_method(request.user.country, request.POST.get("method", ""))
        if method and method.get("provider"):
            # MTN MoMo / Moov Money : push sur le téléphone, confirmation par webhook (module payments).
            try:
                tx = start_mobile_money(order, method, request.POST.get("phone", ""),
                                        request.build_absolute_uri(reverse("payments:webhook")))
            except PurchaseError as exc:
                messages.error(request, str(exc))
            else:
                return redirect("payments:status", pk=tx.pk)
            return render(request, "orders/pay.html", _pay_context(request, order, methods))
        try:
            _, ok, message = pay_order(order, request.POST.get("method", ""), request.POST.get("phone", request.user.phone))
        except PurchaseError as exc:
            messages.error(request, str(exc))
        else:
            if ok:
                messages.success(request, "Paiement validé — votre reçu vous a été envoyé par e-mail.")
                return redirect("orders:confirmation", reference=order.reference)
            messages.error(request, message)
    return render(request, "orders/pay.html", _pay_context(request, order, methods))


@login_required
def confirmation(request, reference):
    order = get_object_or_404(Order.objects.select_related("event", "ticket_type"), reference=reference, buyer=request.user, status=Order.Status.PAID)
    return render(request, "orders/confirmation.html", {"order": order, "tickets": order.tickets.all()})


@login_required
def my_space(request):
    today = timezone.localdate()
    orders = (Order.objects.filter(buyer=request.user, status=Order.Status.PAID)
              .select_related("event", "ticket_type").prefetch_related("tickets"))
    upcoming = [o for o in orders if o.event.end_date >= today]
    past = [o for o in orders if o.event.end_date < today]
    tab = "past" if request.GET.get("tab") == "past" else "upcoming"
    return render(request, "orders/my_space.html", {
        "tab": tab, "upcoming": upcoming, "past": past,
        "shown": past if tab == "past" else upcoming,
    })


def _own_ticket(request, reference):
    ticket = get_object_or_404(Ticket.objects.select_related("order__event__organizer", "order__buyer", "order__ticket_type"), reference=reference)
    if ticket.order.buyer_id != request.user.id:
        raise Http404
    return ticket


@login_required
def ticket_view(request, reference):
    ticket = _own_ticket(request, reference)
    card = getattr(request.user, "business_card", None)   # carte de visite liée au porteur du billet
    return render(request, "orders/ticket_view.html", {"ticket": ticket, "card": card})


@login_required
def ticket_pdf_view(request, reference):
    ticket = _own_ticket(request, reference)
    resp = HttpResponse(ticket_pdf(ticket), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="billet-{ticket.reference}.pdf"'
    return resp


def ticket_qr(request, reference):
    ticket = get_object_or_404(Ticket, reference=reference)
    return HttpResponse(qr_png(verify_url(ticket)), content_type="image/png")


def _pdf(content, filename):
    resp = HttpResponse(content, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def receipt_pdf_view(request, reference):
    """Reçu de paiement PDF (uniquement pour l'acheteur, commande payée)."""
    order = get_object_or_404(Order.objects.select_related("event__organizer", "buyer", "ticket_type"),
                              reference=reference, buyer=request.user, status=Order.Status.PAID)
    return _pdf(order_receipt_pdf(order), f"recu-{order.reference}.pdf")


@login_required
def order_tickets_pdf_view(request, reference):
    """Tous les billets d'une commande dans un seul PDF (un billet par page)."""
    order = get_object_or_404(Order.objects.select_related("event__organizer", "buyer", "ticket_type"),
                              reference=reference, buyer=request.user, status=Order.Status.PAID)
    return _pdf(tickets_pdf(order.tickets.all(), title=f"Billets {order.reference}"), f"billets-{order.reference}.pdf")
