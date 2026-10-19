from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.events.models import Evenement


def accueil(request):
    publies = Evenement.objects.filter(statut=Evenement.Statut.PUBLIE).select_related("organisateur")[:6]
    return render(request, "core/accueil.html", {"evenements": publies})


@login_required
def redirection_tableau_de_bord(request):
    if request.user.est_organisateur:
        return redirect("events:dashboard_organisateur")
    return redirect("tickets:mes_tickets")


def a_propos(request):
    return render(request, "core/a_propos.html")
