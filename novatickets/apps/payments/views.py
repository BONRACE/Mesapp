from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.decorators import organisateur_requis

from .forms import DemandeRetraitForm
from .models import Retrait


@organisateur_requis
@require_http_methods(["GET", "POST"])
def retraits(request):
    """Retrait des gains vers les moyens locaux du pays de l'organisateur."""
    solde = request.user.solde_disponible
    form = DemandeRetraitForm(request.POST or None, pays=request.user.pays)
    if request.method == "POST" and form.is_valid():
        montant = Decimal(form.cleaned_data["montant"])
        if montant > solde:
            form.add_error("montant", f"Montant supérieur à votre solde disponible ({solde} FCFA).")
        elif montant < 1000:
            form.add_error("montant", "Le retrait minimum est de 1 000 FCFA.")
        else:
            Retrait.objects.create(
                organisateur=request.user,
                montant=montant,
                moyen=form.cleaned_data["moyen"],
                numero_compte=form.cleaned_data["numero_compte"],
            )
            messages.success(request, "Demande de retrait enregistrée. Versement sous 24 h ouvrées.")
            return redirect("payments:retraits")
    historique = request.user.retraits.all()
    return render(request, "payments/retraits.html", {"form": form, "solde": solde, "historique": historique})
