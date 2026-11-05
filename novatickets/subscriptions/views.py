from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import organizer_required
from payments.models import Transaction
from payments.services import PaymentError

from . import services
from .forms import SubscribeForm, grouped_methods


@organizer_required
def index(request):
    return render(request, "subscriptions/index.html", {
        "price": services.price(), "days": services.duration_days(), "until": services.active_until(request.user),
        "required": services.required(), "groups": grouped_methods(request.user.country),
        "history": request.user.subscriptions.filter(is_paid=True)[:10],
    })


@organizer_required
@require_POST
def pay(request):
    form = SubscribeForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, " ".join(form.non_field_errors()) or "Choisissez un moyen de paiement.")
        return redirect("subscriptions:index")
    try:
        result = services.start_payment(request.user, form.cleaned_data["method_obj"], form.cleaned_data["phone"],
                                        request.build_absolute_uri(reverse("payments:webhook")))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("subscriptions:index")
    if isinstance(result, Transaction):          # Mobile Money MTN / Moov : suivi du push
        return redirect("payments:status", pk=result.pk)
    messages.success(request, "Abonnement activé. Un reçu vous a été envoyé par e-mail.")
    return redirect("subscriptions:index")
