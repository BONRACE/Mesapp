from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core import cards
from core.countries import withdrawal_methods_for
from core.forms import CardForm
from core.models import BusinessCard
from events.models import Event
from orders.models import Order, Withdrawal


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
    # Page « Mes billets » : accessible aux spectateurs ET aux organisateurs
    # (un organisateur peut acheter, pour lui ou pour un ami, chez un autre organisateur).
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


# ------------------------------------------------------------------ Cartes de visite
def _own_card(request, pk):
    return get_object_or_404(BusinessCard, pk=pk, user=request.user)


@login_required
def card_list(request):
    return render(request, "core/card_list.html", {"cards": request.user.cards.all()})


@login_required
def card_create(request):
    user = request.user
    initial = {"contact_name": user.display_name, "phone": user.phone, "email": user.email}
    if user.is_organisateur:
        initial["company_name"] = user.org_name
    form = CardForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        card = form.save(commit=False)
        card.user = user
        card.save()
        messages.success(request, "Carte de visite créée. Téléchargez-la ci-dessous.")
        return redirect(card)
    return render(request, "core/card_form.html", {"form": form, "editing": False})


@login_required
def card_edit(request, pk):
    card = _own_card(request, pk)
    form = CardForm(request.POST or None, request.FILES or None, instance=card)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Carte de visite mise à jour.")
        return redirect(card)
    return render(request, "core/card_form.html", {"form": form, "editing": True, "card": card})


@login_required
def card_detail(request, pk):
    return render(request, "core/card_detail.html", {"card": _own_card(request, pk)})


@login_required
@require_POST
def card_delete(request, pk):
    _own_card(request, pk).delete()
    messages.success(request, "Carte de visite supprimée.")
    return redirect("core:card_list")


def _filename(card, suffix):
    return f"carte-{slugify(card.company_name) or 'visite'}-{suffix}"


@login_required
def card_image(request, pk, side):
    if side not in ("recto", "verso"):
        raise Http404
    card = _own_card(request, pk)
    resp = HttpResponse(cards.card_png(card, side), content_type="image/png")
    if request.GET.get("dl"):
        resp["Content-Disposition"] = f'attachment; filename="{_filename(card, side)}.png"'
    return resp


@login_required
def card_pdf(request, pk):
    card = _own_card(request, pk)
    resp = HttpResponse(cards.card_pdf(card), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(card, "recto-verso")}.pdf"'
    return resp


@login_required
def card_vcf(request, pk):
    card = _own_card(request, pk)
    resp = HttpResponse(cards.vcard_text(card), content_type="text/vcard; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(card, "contact")}.vcf"'
    return resp
