from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import OnboardingForm, OTPForm, PhoneForm
from .otp import issue_otp, verify_otp

SESSION_PHONE_KEY = "otp_phone"


def login_phone(request):
    """Étape 1 : saisie du numéro, envoi du code."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone_number"]
        if issue_otp(phone):
            request.session[SESSION_PHONE_KEY] = phone
            return redirect("accounts:verify")
        form.add_error(None, "Trop de demandes de code pour ce numéro. Réessayez plus tard.")
    return render(request, "accounts/login.html", {"form": form})


def verify(request):
    """Étape 2 : saisie du code OTP puis ouverture de session."""
    phone = request.session.get(SESSION_PHONE_KEY)
    if not phone:
        return redirect("accounts:login")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_otp(phone, form.cleaned_data["code"]):
            user = authenticate(request, phone_number=phone, verified=True)
            request.session.pop(SESSION_PHONE_KEY, None)
            login(request, user)
            return redirect("accounts:onboarding" if not user.is_onboarded else "core:dashboard")
        form.add_error("code", "Code invalide ou expiré.")
    return render(request, "accounts/verify.html", {"form": form, "phone": phone})


@require_POST
def resend(request):
    phone = request.session.get(SESSION_PHONE_KEY)
    if not phone:
        return redirect("accounts:login")
    if issue_otp(phone):
        messages.success(request, "Un nouveau code vient d'être envoyé.")
    else:
        messages.error(request, "Limite de demandes atteinte. Réessayez plus tard.")
    return redirect("accounts:verify")


@login_required
def onboarding(request):
    """Étape 3 : rôle et profil, obligatoires avant d'accéder aux tableaux de bord."""
    if request.user.is_onboarded:
        return redirect("core:dashboard")
    form = OnboardingForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil créé. Bienvenue sur EcoKolekt.")
        return redirect("core:dashboard")
    return render(request, "accounts/onboarding.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:landing")
