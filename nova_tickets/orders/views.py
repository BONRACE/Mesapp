from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

import io

from core.countries import payment_methods_for
from events.models import Event, TicketType

from . import services
from .models import Order, Ticket


@login_required
@require_POST
def buy(request, slug):
    event = get_object_or_404(Event, slug=slug, status=Event.PUBLISHED)
    if event.organizer_id == request.user.id:
        messages.error(request, "Vous ne pouvez pas acheter de tickets pour votre propre événement.")
        return redirect(event)
    if not event.sales_open:
        messages.error(request, "La vente de tickets est terminée pour cet événement.")
        return redirect(event)
    tt = get_object_or_404(TicketType, pk=request.POST.get("ticket_type"), event=event)
    try:
        qty = max(1, min(int(request.POST.get("quantity", 1)), 10))
    except ValueError:
        qty = 1
    if tt.remaining < qty:
        messages.error(request, "Stock insuffisant pour cette catégorie.")
        return redirect(event)
    order = Order(user=request.user, event=event, ticket_type=tt, quantity=qty)
    order.compute_amounts()
    order.save()
    return redirect("orders:pay", reference=order.reference)


@login_required
def pay(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)
    if order.is_paid:
        return redirect("core:spectateur_dashboard")
    methods = payment_methods_for(request.user.country)
    if request.method == "POST":
        method = request.POST.get("payment_method")
        phone = request.POST.get("payment_phone", "").strip()
        if method not in methods:
            messages.error(request, "Choisissez un moyen de paiement.")
        elif len("".join(ch for ch in phone if ch.isdigit())) < 6 and method != "Carte bancaire":
            messages.error(request, "Entrez le numéro utilisé pour le paiement.")
        else:
            try:
                order = services.confirm_payment(order, method, phone)
            except services.PaymentError as exc:
                messages.error(request, str(exc))
            else:
                services.send_receipt(order)
                messages.success(request, "Paiement validé ! Votre reçu vous a été envoyé par e-mail.")
                return redirect("core:spectateur_dashboard")
    return render(request, "orders/pay.html", {
        "order": order, "methods": methods,
        "commission": order.commission,
    })


def _own_ticket(request, code):
    ticket = get_object_or_404(Ticket.objects.select_related("order__event__organizer", "order__user", "order__ticket_type"), code=code)
    if ticket.order.user_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied
    return ticket


@login_required
def ticket_view(request, code):
    ticket = _own_ticket(request, code)
    return render(request, "orders/ticket.html", {"ticket": ticket})


@login_required
def ticket_pdf(request, code):
    ticket = _own_ticket(request, code)
    pdf = services.ticket_pdf(ticket)
    return FileResponse(io.BytesIO(pdf), as_attachment=True, filename=f"billet-{ticket.short_code}.pdf", content_type="application/pdf")


def ticket_qr(request, code):
    ticket = get_object_or_404(Ticket, code=code)
    return HttpResponse(services.qr_png(ticket.verify_url()), content_type="image/png")


def verify(request, code):
    """Page de contrôle ouverte en scannant le QR code."""
    ticket = get_object_or_404(Ticket.objects.select_related("order__event", "order__user", "order__ticket_type"), code=code)
    can_validate = request.user.is_authenticated and ticket.order.event.organizer_id == request.user.id
    if request.method == "POST" and can_validate and not ticket.used:
        ticket.used = True
        ticket.save(update_fields=["used"])
        messages.success(request, "Billet validé : entrée autorisée.")
        return redirect("orders:verify", code=code)
    return render(request, "orders/verify.html", {"ticket": ticket, "can_validate": can_validate})
