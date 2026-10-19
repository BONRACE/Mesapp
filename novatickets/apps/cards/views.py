from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import spectateur_requis
from apps.core.emails import envoyer_carte_visite_prete
from apps.core.pdf import PdfIndisponible, rendre_pdf
from apps.core.qr import qr_svg_data_uri
from apps.payments.models import Paiement
from apps.payments.providers import get_provider, moyens_pour_pays

from .forms import CarteVisiteForm
from .models import CarteVisite

def _prix():
    from django.conf import settings

    return settings.NOVATICKETS["PRIX_CARTE_VISITE"]


@spectateur_requis
def liste(request):
    return render(request, "cards/liste.html", {"cartes": request.user.cartes_visite.all(), "prix": _prix()})


@spectateur_requis
@require_http_methods(["GET", "POST"])
def creer(request):
    """Éditeur avec aperçu en direct. Enregistre le brouillon, puis paiement."""
    form = CarteVisiteForm(request.POST or None, request.FILES or None, initial={"email": request.user.email, "telephone": request.user.telephone_complet})
    if request.method == "POST" and form.is_valid():
        carte = form.save(commit=False)
        carte.utilisateur = request.user
        carte.save()
        return redirect("cards:paiement", pk=carte.pk)
    return render(request, "cards/editeur.html", {"form": form, "prix": _prix()})


@spectateur_requis
@require_http_methods(["GET", "POST"])
def paiement(request, pk):
    """Paiement obligatoire (100 FCFA) avant toute génération."""
    carte = get_object_or_404(CarteVisite, pk=pk, utilisateur=request.user)
    if carte.paye:
        return redirect("cards:telecharger", pk=carte.pk)
    moyens = moyens_pour_pays(request.user.pays)
    if request.method == "POST":
        slug = request.POST.get("moyen", "")
        provider = get_provider(slug)
        if provider is None:
            messages.error(request, "Choisissez un moyen de paiement valide.")
            return redirect("cards:paiement", pk=carte.pk)
        paiement = Paiement.objects.create(
            utilisateur=request.user,
            objet=Paiement.Objet.CARTE,
            montant=_prix(),
            fournisseur=slug,
            telephone_payeur=request.POST.get("telephone_payeur", request.user.telephone_complet),
        )
        resultat = provider.initier(paiement, paiement.telephone_payeur)
        if resultat.succes:
            paiement.reference_externe = resultat.reference_externe
            paiement.statut = Paiement.Statut.REUSSI
            paiement.termine_le = timezone.now()
            paiement.save()
            carte.paye = True
            carte.paiement = paiement
            carte.genere_le = timezone.now()
            carte.save()
            envoyer_carte_visite_prete(carte)
            messages.success(request, "Paiement validé. Votre carte de visite est générée !")
            return redirect("cards:telecharger", pk=carte.pk)
        paiement.statut = Paiement.Statut.ECHOUE
        paiement.save(update_fields=["statut"])
        messages.error(request, "Le paiement n'a pas abouti. Aucune carte n'a été générée.")
    return render(request, "cards/paiement.html", {"carte": carte, "moyens": moyens, "prix": _prix()})


@spectateur_requis
def telecharger(request, pk):
    carte = get_object_or_404(CarteVisite, pk=pk, utilisateur=request.user)
    if not carte.generee:
        messages.error(request, "Cette carte n'est pas encore payée : téléchargement impossible.")
        return redirect("cards:paiement", pk=carte.pk)
    try:
        return rendre_pdf("cards/carte_pdf.html", {"carte": carte, "qr": qr_svg_data_uri(f"NT-CARTE-{carte.pk}")}, f"carte-visite-{carte.pk}.pdf")
    except PdfIndisponible as exc:
        messages.error(request, str(exc))
        return redirect("cards:liste")


@spectateur_requis
@require_POST
def supprimer(request, pk):
    carte = get_object_or_404(CarteVisite, pk=pk, utilisateur=request.user)
    if carte.paye:
        messages.error(request, "Une carte payée ne peut pas être supprimée.")
    else:
        carte.delete()
        messages.success(request, "Brouillon supprimé.")
    return redirect("cards:liste")
