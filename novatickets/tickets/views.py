from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from events.models import Event

from .forms import PurchaseForm
from .models import Order, Ticket
from .pdf import tickets_pdf
from .qr import qr_png, ticket_url
from .services import create_order


# --- Achat ---------------------------------------------------------------------------

@login_required
def buy(request, slug):
    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), slug=slug, is_published=True)
    if event.organizer_id == request.user.id:
        messages.error(request, "Vous ne pouvez pas acheter de tickets pour votre propre événement.")
        return redirect(event)
    initial = {}
    if request.GET.get("type"):
        initial["ticket_type"] = request.GET["type"]
    form = PurchaseForm(request.POST or None, request.FILES or None, event=event, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        order, payment = create_order(request.user, d["ticket_type"], d["quantity"], form.recipient())
        if payment.is_succeeded:  # ticket gratuit
            messages.success(request, "Ticket confirmé ! Un reçu vous a été envoyé par e-mail.")
            return redirect(payment.get_success_url())
        return redirect(payment.get_checkout_url())
    return render(request, "tickets/buy.html", {"event": event, "form": form})


# --- Espace « mes billets » (spectateur ou organisateur) ----------------------------------

@login_required
def dashboard(request):
    orders = Order.objects.filter(buyer=request.user).select_related("event", "ticket_type").prefetch_related("tickets")
    paid = [o for o in orders if o.is_paid]
    upcoming = [t for o in paid if o.is_upcoming for t in o.tickets.all()]
    past = [t for o in paid if not o.is_upcoming for t in o.tickets.all()]
    return render(request, "tickets/dashboard.html", {
        "orders": orders, "upcoming": upcoming, "past": past,
        "upcoming_orders": [o for o in orders if o.is_upcoming],
        "past_orders": [o for o in orders if not o.is_upcoming],
    })


def _my_order(request, reference):
    return get_object_or_404(Order.objects.select_related("event", "ticket_type", "event__organizer"),
                             reference=reference, buyer=request.user)


def _my_ticket(request, reference):
    return get_object_or_404(
        Ticket.objects.select_related("order", "order__event", "order__ticket_type", "order__event__organizer", "order__buyer"),
        reference=reference, order__buyer=request.user, order__status=Order.Status.PAID)


@login_required
def order_detail(request, reference):
    order = _my_order(request, reference)
    return render(request, "tickets/order_detail.html", {"order": order, "tickets": order.tickets.all()})


@login_required
def ticket_detail(request, reference):
    ticket = _my_ticket(request, reference)
    return render(request, "tickets/ticket_detail.html", {"ticket": ticket})


def _pdf(data, name):
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
    return resp


@login_required
def ticket_pdf(request, reference):
    ticket = _my_ticket(request, reference)
    return _pdf(tickets_pdf([ticket]), f"ticket-{ticket.reference}")


@login_required
def order_pdf(request, reference):
    order = _my_order(request, reference)
    if not order.is_paid:
        raise Http404
    return _pdf(tickets_pdf(order.tickets.all()), f"tickets-{order.reference}")


@login_required
def ticket_qr(request, reference):
    ticket = _my_ticket(request, reference)
    return HttpResponse(qr_png(ticket_url(ticket), 10), content_type="image/png")


# --- Vérification à l'entrée (URL encodée dans le QR code) ---------------------------------

def verify(request, token):
    ticket = get_object_or_404(
        Ticket.objects.select_related("order", "order__event", "order__ticket_type", "order__event__organizer"),
        token=token, order__status=Order.Status.PAID)
    is_organizer = request.user.is_authenticated and ticket.event.organizer_id == request.user.id
    return render(request, "tickets/verify.html", {"ticket": ticket, "is_organizer": is_organizer})


@login_required
def mark_used(request, token):
    """Seul l'organisateur de l'événement peut valider une entrée."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    ticket = get_object_or_404(Ticket.objects.select_related("order__event"), token=token,
                               order__status=Order.Status.PAID, order__event__organizer=request.user)
    if ticket.used_at:
        messages.error(request, "Ce ticket a déjà été utilisé.")
    else:
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["used_at"])
        messages.success(request, "Entrée validée.")
    return redirect("tickets:verify", token=token)
