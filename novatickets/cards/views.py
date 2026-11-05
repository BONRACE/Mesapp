from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from orders.services import qr_png

from .palettes import rgb
from payments.services import PaymentError

from .pdf import card_pdf
from .forms import ActivationForm, BusinessCardForm
from .models import BusinessCard
from .services import card_price, linked_ticket, start_activation, vcard


def _initial_for(user):
    """Pré-remplit la carte avec le profil (modifiable) : l'utilisateur n'a presque rien à saisir."""
    return {"full_name": user.display_name, "email": user.email, "phone": user.phone,
            "company": user.org_name, "job_title": user.profession}


@login_required
def edit(request):
    """Création / modification de ma carte, aperçu, partage et activation."""
    card = BusinessCard.objects.filter(user=request.user).first()
    form = BusinessCardForm(request.POST or None, instance=card, initial=None if card else _initial_for(request.user))
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.save()
        messages.success(request, "Carte enregistrée.")
        return redirect("cards:edit")
    # Sans carte enregistrée, on montre quand même un aperçu (brouillon non enregistré, pré-rempli) : on voit
    # tout de suite les styles « Pagne », les couleurs, etc. dès la création.
    draft = card or BusinessCard(user=request.user, **_initial_for(request.user))
    return render(request, "cards/edit.html", {
        "form": form, "card": card, "draft": draft, "price": card_price(), "activation_form": ActivationForm(),
    })


@login_required
def my_card_pdf(request):
    """Ma carte en PDF (téléchargement, ou affichage direct avec ?inline=1 pour l'impression). Réservé aux cartes activées (payées)."""
    card = get_object_or_404(BusinessCard.objects.select_related("user"), user=request.user)
    if not card.is_active:
        messages.error(request, "Activez votre carte (paiement) pour la télécharger ou l'imprimer.")
        return redirect("cards:edit")
    resp = HttpResponse(card_pdf(card), content_type="application/pdf")
    resp["Content-Disposition"] = f'{"inline" if request.GET.get("inline") else "attachment"}; filename="carte-{card.slug}.pdf"'
    return resp


@login_required
@require_POST
def activate(request):
    """Active la carte : directement si gratuite, sinon paiement Mobile Money puis page de suivi."""
    card = get_object_or_404(BusinessCard, user=request.user)
    if card.is_active:
        return redirect("cards:edit")
    form = ActivationForm(request.POST)
    if card_price() > 0 and not form.is_valid():
        messages.error(request, "Choisissez un opérateur et saisissez votre numéro Mobile Money.")
        return redirect("cards:edit")
    data = form.cleaned_data if form.is_valid() else {"provider": "MTN", "phone": ""}
    try:
        tx = start_activation(card, data["provider"], data["phone"], request.build_absolute_uri(reverse("payments:webhook")))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("cards:edit")
    if tx is None:
        messages.success(request, "Carte activée : vous pouvez la partager.")
        return redirect("cards:edit")
    return redirect("payments:status", pk=tx.pk)


def _visible_card(request, slug):
    """Une carte non activée n'est visible que par son propriétaire (aperçu)."""
    card = get_object_or_404(BusinessCard.objects.select_related("user"), slug=slug)
    if not card.is_active and not (request.user.is_authenticated and card.user_id == request.user.id):
        raise Http404
    return card


def public(request, slug):
    """Page publique de la carte (ouverte via le lien ou le QR code partagé depuis le billet)."""
    card = _visible_card(request, slug)
    ticket = linked_ticket(card, request.GET.get("billet", ""))   # ?billet=TK-… : lien depuis le billet du participant
    return render(request, "cards/public.html", {"card": card, "preview": not card.is_active, "ticket": ticket})


def download_vcard(request, slug):
    """Fichier .vcf : « Enregistrer dans mes contacts »."""
    card = _visible_card(request, slug)
    resp = HttpResponse(vcard(card), content_type="text/vcard; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{card.slug}.vcf"'
    return resp


def qr(request, slug):
    card = _visible_card(request, slug)
    ticket = linked_ticket(card, request.GET.get("billet", ""))
    url = card.public_url + (f"?billet={ticket.reference}" if ticket else "")
    return HttpResponse(qr_png(url, rgb(card.theme)), content_type="image/png")
