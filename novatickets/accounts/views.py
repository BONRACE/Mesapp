from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import LoginForm, OrganisateurRegisterForm, ProfileForm, SpectateurRegisterForm


def home_for(user):
    return reverse("events:orga_dashboard") if user.is_organizer else reverse("orders:my_space")


class NovaLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or home_for(self.request.user)


def register_choice(request):
    return render(request, "accounts/register_choice.html")


def _register(request, form_class, title, subtitle):
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue sur NovaTickets, {user.first_name} !")
        return redirect(home_for(user))
    return render(request, "accounts/register.html", {"form": form, "title": title, "subtitle": subtitle})


def register_spectateur(request):
    return _register(request, SpectateurRegisterForm, "Créer mon compte spectateur", "Achetez vos billets et retrouvez-les à tout moment.")


def register_organisateur(request):
    return _register(request, OrganisateurRegisterForm, "Créer mon compte organisateur", "Publiez vos événements et encaissez vos ventes.")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
