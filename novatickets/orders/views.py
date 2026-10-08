from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.payments import methods_for_country
from events.models import TicketType

from .models import Order, Ticket
from .services import PurchaseError, create_order, pay_order, qr_png, ticket_pdf, verify_url


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


@login_required
def pay(request, reference):
    order = get_object_or_404(Order.objects.select_related("event", "ticket_type"), reference=reference, buyer=request.user)
    if order.status == Order.Status.PAID:
        return redirect("orders:confirmation", reference=order.reference)
    methods = methods_for_country(request.user.country)
    if request.method == "POST":
        try:
            _, ok, message = pay_order(order, request.POST.get("method", ""), request.POST.get("phone", request.user.phone))
        except PurchaseError as exc:
            messages.error(request, str(exc))
        else:
            if ok:
                messages.success(request, "Paiement validé — votre reçu vous a été envoyé par e-mail.")
                return redirect("orders:confirmation", reference=order.reference)
            messages.error(request, message)
    return render(request, "orders/pay.html", {"order": order, "methods": methods})


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
    return render(request, "orders/ticket_view.html", {"ticket": ticket})


@login_required
def ticket_pdf_view(request, reference):
    ticket = _own_ticket(request, reference)
    resp = HttpResponse(ticket_pdf(ticket), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="billet-{ticket.reference}.pdf"'
    return resp


def ticket_qr(request, reference):
    ticket = get_object_or_404(Ticket, reference=reference)
    return HttpResponse(qr_png(verify_url(ticket)), content_type="image/png")
