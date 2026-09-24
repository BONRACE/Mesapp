from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import SpectateurRegisterForm, OrganisateurRegisterForm, ProfileForm


def register_choice(request):
    return render(request, "accounts/register_choice.html")


def register_spectateur(request):
    if request.method == "POST":
        form = SpectateurRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Bienvenue sur NovaTickets ✨")
            return redirect("dashboard_redirect")
    else:
        form = SpectateurRegisterForm()
    return render(request, "accounts/register_spectateur.html", {"form": form})


def register_organisateur(request):
    if request.method == "POST":
        form = OrganisateurRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Espace organisateur créé ✨")
            return redirect("dashboard_redirect")
    else:
        form = OrganisateurRegisterForm()
    return render(request, "accounts/register_organisateur.html", {"form": form})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("accounts:profile_edit")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
