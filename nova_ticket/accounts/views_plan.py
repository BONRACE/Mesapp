"""Souscription au plan Pro (0% de commission) par un organisateur, via FedaPay.

Même mécanique que l'achat d'un billet (tickets.views_paiement) : on crée la transaction,
on redirige vers le `checkout_url` hébergé par FedaPay, et c'est le webhook — pas la page de
retour — qui active réellement l'abonnement à la confirmation du paiement.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from tickets import fedapay_client
from tickets.fedapay_client import FedaPayError
from .models import PlanAbonnement


@login_required
def souscrire_pro(request):
    if not request.user.is_organisateur:
        messages.error(request, "Seul un compte organisateur peut souscrire au plan Pro.")
        return redirect("dashboard_redirect")

    plan = PlanAbonnement.pour(request.user)
    context = {"plan": plan, "prix": settings.PLAN_PRO_PRIX_FCFA}

    if request.method == "POST":
        callback_url = request.build_absolute_uri(reverse("accounts:plan_pro_retour"))
        try:
            transaction_id, checkout_url = fedapay_client.initier_paiement(
                description=f"Abonnement NovaTickets Pro — 1 mois ({request.user.nom_complet})",
                montant=settings.PLAN_PRO_PRIX_FCFA,
                devise="XOF",
                spectateur=request.user,
                callback_url=callback_url,
            )
        except FedaPayError as exc:
            messages.error(request, f"Le paiement n'a pas pu être initié : {exc}")
            return render(request, "accounts/plan_pro.html", context)

        plan.fedapay_transaction_id = str(transaction_id)
        plan.save(update_fields=["fedapay_transaction_id"])
        return redirect(checkout_url)

    return render(request, "accounts/plan_pro.html", context)


@login_required
def plan_pro_retour(request):
    """Page de retour après le paiement de l'abonnement (callback_url) — purement informative,
    comme tickets.views_paiement.paiement_retour. Le webhook valide l'abonnement en coulisses."""
    plan = PlanAbonnement.pour(request.user)
    return render(request, "accounts/plan_pro_retour.html", {"plan": plan})
