from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import (
    ConnexionForm,
    InscriptionOrganisateurForm,
    InscriptionSpectateurForm,
    ProfilForm,
    ProfilOrganisateurForm,
)
from .models import ProfilOrganisateur


def _connecter(request, utilisateur):
    utilisateur.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, utilisateur)


@require_http_methods(["GET", "POST"])
def inscription_spectateur(request):
    if request.user.is_authenticated:
        return redirect("core:redirection_tableau_de_bord")
    form = InscriptionSpectateurForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        _connecter(request, utilisateur)
        messages.success(request, f"Bienvenue {utilisateur.first_name} ! Votre compte spectateur est prêt.")
        return redirect("core:redirection_tableau_de_bord")
    return render(request, "accounts/inscription.html", {"form": form, "mode": "spectateur"})


@require_http_methods(["GET", "POST"])
def inscription_organisateur(request):
    if request.user.is_authenticated:
        return redirect("core:redirection_tableau_de_bord")
    form = InscriptionOrganisateurForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        _connecter(request, utilisateur)
        messages.success(request, "Compte organisateur créé. Publiez votre premier événement !")
        return redirect("core:redirection_tableau_de_bord")
    return render(request, "accounts/inscription.html", {"form": form, "mode": "organisateur"})


@require_http_methods(["GET", "POST"])
def connexion(request):
    if request.user.is_authenticated:
        return redirect("core:redirection_tableau_de_bord")
    form = ConnexionForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "core:redirection_tableau_de_bord")
    return render(request, "accounts/connexion.html", {"form": form})


@require_http_methods(["POST"])
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("core:accueil")


@login_required
@require_http_methods(["GET", "POST"])
def profil(request):
    form = ProfilForm(request.POST or None, request.FILES or None, instance=request.user)
    profil_org = getattr(request.user, "profil_organisateur", None) if request.user.est_organisateur else None
    form_org = ProfilOrganisateurForm(request.POST or None, request.FILES or None, instance=profil_org) if profil_org else None

    if request.method == "POST":
        valide = form.is_valid() and (form_org is None or form_org.is_valid())
        if valide:
            form.save()
            if form_org:
                form_org.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("accounts:profil")
    return render(request, "accounts/profil.html", {"form": form, "form_org": form_org})
