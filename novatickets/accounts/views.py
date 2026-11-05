from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
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


class ThrottledPasswordResetView(PasswordResetView):
    """Mot de passe oublié limité par IP (RESET_MAX_PER_HOUR/h) : évite le bombardement d'e-mails.

    Au-delà de la limite, la réponse reste identique (« e-mail envoyé ») mais rien n'est envoyé : aucun signal exploitable."""

    def form_valid(self, form):
        from django.http import HttpResponseRedirect

        from . import throttle
        if throttle.hit_hourly(self.request, "reset"):
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)


def register_choice(request):
    """Le choix Spectateur / Organisateur se fait avec les onglets de la page d'inscription."""
    return redirect("accounts:register_spectateur")


def _register(request, form_class, title, subtitle):
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue sur NovaTickets, {user.first_name} !")
        return redirect(home_for(user))
    return render(request, "accounts/register.html", {"form": form, "title": title, "subtitle": subtitle, "role": form.role})


def register_spectateur(request):
    return _register(request, SpectateurRegisterForm, "Créer un compte spectateur", "Achetez vos billets et retrouvez-les à tout moment.")


def register_organisateur(request):
    return _register(request, OrganisateurRegisterForm, "Créer un compte organisateur", "Publiez vos événements et encaissez vos ventes.")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("accounts:profile")
    from .services import blockers
    return render(request, "accounts/profile.html", {"form": form, "delete_blockers": blockers(request.user)})


@login_required
def delete_account_view(request):
    """Confirmation (mot de passe + mot « SUPPRIMER ») puis anonymisation définitive du compte."""
    from django.contrib.auth import logout

    from .services import CONFIRM_WORD, blockers, delete_account

    if request.user.is_organizer:               # la suppression en libre-service n'existe pas pour les organisateurs
        messages.info(request, "La suppression de compte n'est pas disponible pour un compte organisateur. Contactez le support.")
        return redirect("accounts:profile")
    reasons = blockers(request.user)
    if request.method == "POST":
        if reasons:
            messages.error(request, "Suppression impossible pour le moment.")
        elif not request.user.check_password(request.POST.get("password", "")):
            messages.error(request, "Mot de passe incorrect.")
        elif request.POST.get("confirm", "").strip().upper() != CONFIRM_WORD:
            messages.error(request, f"Tapez {CONFIRM_WORD} pour confirmer.")
        else:
            delete_account(request.user)
            logout(request)
            messages.success(request, "Votre compte a été supprimé. Merci d'avoir utilisé NovaTickets.")
            return redirect("core:home")
    return render(request, "accounts/delete.html", {"reasons": reasons, "word": CONFIRM_WORD})
