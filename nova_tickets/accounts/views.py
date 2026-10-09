from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render

from core.countries import all_countries

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import User


class NovaLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request, role):
    if role not in (User.SPECTATEUR, User.ORGANISATEUR):
        return redirect("core:home")
    if request.user.is_authenticated:
        return redirect("core:dashboard_redirect")
    form = RegisterForm(request.POST or None, request.FILES or None, role=role)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue sur NovaTickets, {user.first_name} !")
        return redirect("core:dashboard_redirect")
    return render(request, "accounts/register.html", {"form": form, "role": role, "countries": all_countries()})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "countries": all_countries()})
