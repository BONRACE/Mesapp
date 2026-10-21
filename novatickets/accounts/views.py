from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from core.countries import all_countries

from .forms import LoginForm, ProfileForm, RegisterForm


class NovaLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def register_choice(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "accounts/register_choice.html")


def register(request, role):
    if role not in ("spectateur", "organisateur"):
        raise Http404
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = RegisterForm(request.POST or None, request.FILES or None, role=role)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailBackend")
        messages.success(request, f"Bienvenue sur NovaTickets, {user.first_name} !")
        nxt = request.GET.get("next", "")
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            return redirect(nxt)
        return redirect("core:dashboard")
    return render(
        request,
        "accounts/register.html",
        {"form": form, "role": role, "countries": all_countries()},
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "countries": all_countries()})
