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

import re
from decimal import Decimal as _D

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseBadRequest

from core import card_mail, cards
from core.cardkit import CardData, open_logo
from core.countries import payment_methods_for, withdrawal_methods_for
from core.forms import CardForm
from core.models import BusinessCard, CardPayment
from orders import services as order_services
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


def _form_context(form, editing, card=None):
    return {"form": form, "editing": editing, "card": card, "templates": [(k, v["label"], v["hint"]) for k, v in cards.TEMPLATES.items()],
            "colors": BusinessCard.COLORS}


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
        messages.success(request, "Votre carte est créée. Validez-la pour obtenir les fichiers en haute définition.")
        return redirect(card)
    return render(request, "core/card_form.html", _form_context(form, False))


@login_required
def card_edit(request, pk):
    card = _own_card(request, pk)
    form = CardForm(request.POST or None, request.FILES or None, instance=card)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Carte de visite mise à jour.")
        return redirect(card)
    return render(request, "core/card_form.html", _form_context(form, True, card))


@login_required
def card_detail(request, pk):
    return render(request, "core/card_detail.html", {"card": _own_card(request, pk),
                                                      "sides": [("recto", "Recto"), ("verso", "Verso")]})


@login_required
@require_POST
def card_delete(request, pk):
    _own_card(request, pk).delete()
    messages.success(request, "Carte de visite supprimée.")
    return redirect("core:card_list")


def _filename(card, suffix):
    return f"carte-{slugify(card.company_name) or 'visite'}-{suffix}"


def _need_payment(request, card):
    messages.info(request, f"Validez votre carte ({settings.BUSINESS_CARD_PRICE} FCFA) pour télécharger les fichiers.")
    return redirect("core:card_pay", pk=card.pk)


@login_required
def card_image(request, pk, side):
    """Carte payée : fichier final HD. Sinon : aperçu basse définition filigrané (jamais le fichier final)."""
    if side not in ("recto", "verso"):
        raise Http404
    card = _own_card(request, pk)
    if not card.is_paid:
        if request.GET.get("dl"):
            return _need_payment(request, card)
        resp = HttpResponse(cards.preview_png(cards.data_from_card(card), side), content_type="image/png")
        resp["Cache-Control"] = "private, max-age=0"
        return resp
    resp = HttpResponse(cards.card_png(card, side), content_type="image/png")
    if request.GET.get("dl"):
        resp["Content-Disposition"] = f'attachment; filename="{_filename(card, side)}.png"'
    return resp


@login_required
def card_pdf(request, pk):
    card = _own_card(request, pk)
    if not card.is_paid:
        return _need_payment(request, card)
    resp = HttpResponse(cards.card_pdf(card), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(card, "recto-verso")}.pdf"'
    return resp


@login_required
def card_vcf(request, pk):
    card = _own_card(request, pk)
    if not card.is_paid:
        return _need_payment(request, card)
    resp = HttpResponse(cards.vcard_text(card), content_type="text/vcard; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(card, "contact")}.vcf"'
    return resp


# --- aperçu en direct et miniatures des modèles
_LIMITS = {"company": 80, "tagline": 100, "name": 80, "title": 80, "phone": 30, "email": 120, "website": 120,
           "address": 160, "social": 60}
_FIELDS = {"company": "company_name", "tagline": "tagline", "name": "contact_name", "title": "job_title",
           "phone": "phone", "email": "email", "website": "website", "address": "address", "social": "social"}
_MAX_LOGO = 5 * 1024 * 1024


@login_required
@require_POST
def card_preview(request, side):
    """Aperçu filigrané de ce qui est en cours de saisie (rien n'est enregistré)."""
    if side not in ("recto", "verso"):
        raise Http404
    P = request.POST
    values = {k: P.get(f, "").strip()[:_LIMITS[k]] for k, f in _FIELDS.items()}
    template = P.get("template") if P.get("template") in dict(BusinessCard.TEMPLATES) else "atelier"
    color = P.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", P.get("color", "")) else "#059669"
    logo = None
    up = request.FILES.get("logo")
    if up is not None:
        if up.size > _MAX_LOGO:
            return HttpResponseBadRequest("Logo trop lourd (5 Mo maximum).")
        logo = open_logo(up)
    elif P.get("card_id", "").isdigit():
        card = BusinessCard.objects.filter(pk=P["card_id"], user=request.user).first()
        logo = open_logo(card.logo) if card and card.logo else None
    if logo is None and not up:
        logo = open_logo(getattr(request.user, "org_logo", None)) if not P.get("no_org_logo") else None
    data = CardData(**values, template=template, color=color, logo=logo)
    return HttpResponse(cards.preview_png(data, side), content_type="image/png")


@login_required
def card_sample(request, template, color, side):
    if template not in cards.TEMPLATES or side not in ("recto", "verso") or not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        raise Http404
    resp = HttpResponse(cards.sample_png(template, "#" + color.lower(), side), content_type="image/png")
    resp["Cache-Control"] = "private, max-age=86400"
    return resp


# --- paiement des 100 FCFA
def _notify_card_receipt(request, sent, payment):
    if not sent:
        messages.warning(request, "Paiement validé ! Mais l'e-mail de confirmation n'a pas pu partir : "
                                  "téléchargez vos fichiers ci-dessous.")
    elif order_services.email_is_console():
        messages.info(request, "Paiement validé ! Mode développement : l'e-mail s'affiche dans le terminal du serveur "
                               "(configurez la section E-mails du fichier .env pour l'envoyer).")
    else:
        messages.success(request, f"Paiement validé ! Votre carte et son PDF ont été envoyés à {payment.user.email}.")


@login_required
def card_pay(request, pk):
    card = _own_card(request, pk)
    if card.is_paid:
        return redirect(card)
    methods = payment_methods_for(request.user.country)
    price = settings.BUSINESS_CARD_PRICE
    if request.method == "POST":
        method = request.POST.get("payment_method")
        phone = request.POST.get("payment_phone", "").strip()
        if method not in methods:
            messages.error(request, "Choisissez un moyen de paiement.")
        elif len("".join(ch for ch in phone if ch.isdigit())) < 6 and method != "Carte bancaire":
            messages.error(request, "Entrez le numéro utilisé pour le paiement.")
        else:
            payment = CardPayment.objects.create(card=card, user=request.user, amount=_D(price), method=method,
                                                 phone=phone)
            try:
                order_services.charge(payment, method, phone)
            except order_services.PaymentError as exc:
                payment.status = CardPayment.FAILED
                payment.save(update_fields=["status"])
                messages.error(request, str(exc))
            else:
                with transaction.atomic():
                    payment.status = CardPayment.PAID
                    payment.save(update_fields=["status"])
                    BusinessCard.objects.filter(pk=card.pk, paid_at__isnull=True).update(paid_at=timezone.now())
                card.refresh_from_db()
                _notify_card_receipt(request, card_mail.send_card_receipt(payment), payment)
                return redirect(card)
    return render(request, "core/card_pay.html", {"card": card, "methods": methods, "price": price})
