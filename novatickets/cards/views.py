from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings

from payments.services import create_payment

from . import render as renderer
from .forms import BusinessCardForm
from .models import BusinessCard

SIDES = ("recto", "verso")


def _own_card(request, pk):
    return get_object_or_404(BusinessCard, pk=pk, owner=request.user)


@login_required
def card_list(request):
    return render(request, "cards/list.html", {"cards": request.user.business_cards.all()})


def _form_page(request, form, card=None):
    return render(request, "cards/form.html", {
        "form": form, "card": card, "themes": BusinessCard.Theme.choices,
        "price": settings.BUSINESS_CARD_PRICE,
    })


@login_required
def card_create(request):
    form = BusinessCardForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        card = form.save(commit=False)
        card.owner = request.user
        card.save()
        messages.success(request, "Carte enregistrée. Payez pour la générer et la télécharger.")
        return redirect(card)
    return _form_page(request, form)


@login_required
def card_edit(request, pk):
    card = _own_card(request, pk)
    if card.is_paid:
        messages.error(request, "Cette carte est déjà générée : créez-en une nouvelle pour la modifier.")
        return redirect(card)
    form = BusinessCardForm(request.POST or None, request.FILES or None, instance=card)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Carte mise à jour.")
        return redirect(card)
    return _form_page(request, form, card)


@login_required
def card_detail(request, pk):
    card = _own_card(request, pk)
    return render(request, "cards/detail.html", {"card": card, "price": settings.BUSINESS_CARD_PRICE})


@login_required
def card_pay(request, pk):
    """Crée le paiement de 100 FCFA et envoie vers la page de paiement commune."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    card = _own_card(request, pk)
    if card.is_paid:
        return redirect(card)
    payment = create_payment(request.user, "card", settings.BUSINESS_CARD_PRICE, card=card)
    return redirect(payment.get_checkout_url())


@login_required
def card_delete(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    card = _own_card(request, pk)
    if card.payments.exists():
        messages.error(request, "Une carte payée ne peut pas être supprimée.")
        return redirect(card)
    card.delete()
    messages.success(request, "Carte supprimée.")
    return redirect("cards:list")


def _png(data):
    resp = HttpResponse(data, content_type="image/png")
    resp["Cache-Control"] = "private, max-age=0, no-store"
    return resp


@login_required
def live_preview(request):
    """Aperçu en direct : reçoit le formulaire (POST), renvoie un PNG filigrané."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    side = request.POST.get("side", "recto")
    theme = request.POST.get("theme", "emeraude")
    if side not in SIDES or theme not in renderer.THEMES:
        raise Http404
    get = lambda k, n: request.POST.get(k, "").strip()[:n]  # noqa: E731
    logo = request.FILES.get("logo")
    if logo is None and request.POST.get("card"):  # carte existante : logo déjà enregistré
        existing = BusinessCard.objects.filter(pk=request.POST["card"], owner=request.user).first()
        logo = existing.logo if existing and existing.logo else None
    card = SimpleNamespace(
        theme=theme, company_name=get("company_name", 80) or "Nom de l'entreprise",
        contact_name=get("contact_name", 80) or "Nom du contact", job_title=get("job_title", 80),
        phone=get("phone", 30), email=get("email", 120), website=get("website", 120),
        address=get("address", 160), tagline=get("tagline", 90), logo=logo,
    )
    return _png(renderer.png_bytes(card, side, scale=.6, watermark=True))


@login_required
def saved_preview(request, pk, side):
    """Aperçu d'une carte enregistrée ; filigrané tant qu'elle n'est pas payée."""
    card = _own_card(request, pk)
    if side not in SIDES:
        raise Http404
    return _png(renderer.png_bytes(card, side, scale=.7, watermark=not card.is_paid))


def theme_sample(request, theme, side):
    if theme not in renderer.THEMES or side not in SIDES:
        raise Http404
    resp = HttpResponse(renderer.sample_png(theme, side), content_type="image/png")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


@login_required
def download(request, pk, fmt):
    """Génération finale : réservée aux cartes dont le paiement est validé."""
    card = _own_card(request, pk)
    if not card.is_paid:
        messages.error(request, f"Payez {settings.BUSINESS_CARD_PRICE} FCFA pour générer cette carte.")
        return redirect(card)
    slug = "".join(c if c.isalnum() else "-" for c in card.company_name.lower()).strip("-") or "carte"
    if fmt == "pdf":
        resp = HttpResponse(renderer.card_pdf(card), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="carte-{slug}.pdf"'
    elif fmt in SIDES:
        resp = HttpResponse(renderer.png_bytes(card, fmt), content_type="image/png")
        resp["Content-Disposition"] = f'attachment; filename="carte-{slug}-{fmt}.png"'
    else:
        raise Http404
    return resp
