from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import organisateur_required

from .forms import CheckoutForm, WithdrawalForm
from .models import Payment, Withdrawal
from .services import organizer_balance, process_payment, request_withdrawal


@login_required
def checkout(request, reference):
    """Page de paiement commune aux tickets et aux cartes de visite."""
    payment = get_object_or_404(Payment.objects.select_related("order", "business_card"),
                                reference=reference, user=request.user)
    if payment.is_succeeded:
        return redirect(payment.get_success_url())
    if payment.status == Payment.Status.REFUNDED:
        return render(request, "payments/checkout.html", {"payment": payment, "form": None})
    form = CheckoutForm(request.POST or None, country=request.user.country,
                        initial={"method": "", "phone": request.user.phone})
    if request.method == "POST" and form.is_valid():
        payment = process_payment(payment, form.cleaned_data["method"], form.cleaned_data.get("phone", ""))
        if payment.is_succeeded:
            if payment.order_id:
                messages.success(request, "Paiement validé ! Votre reçu a été envoyé par e-mail.")
            else:
                messages.success(request, "Paiement validé ! Votre carte est prête à être téléchargée.")
            return redirect(payment.get_success_url())
        form.add_error(None, payment.failure_reason or "Le paiement n'a pas abouti.")
    return render(request, "payments/checkout.html", {"payment": payment, "form": form})


@login_required
def history(request):
    return render(request, "payments/history.html", {"payments": request.user.payments.select_related("order", "business_card")})


@organisateur_required
def withdrawals(request):
    balance = organizer_balance(request.user)
    form = WithdrawalForm(request.POST or None, user=request.user, balance=balance,
                          initial={"phone": request.user.phone})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            w = request_withdrawal(request.user, d["amount"], d["method"], d["phone"])
        except ValueError as exc:
            form.add_error("amount", str(exc))
        else:
            if w.status == Withdrawal.Status.COMPLETED:
                messages.success(request, f"Retrait de {w.amount} FCFA effectué vers {w.method_label}.")
            else:
                messages.error(request, w.failure_reason or "Le retrait a échoué.")
            return redirect("payments:withdrawals")
    return render(request, "payments/withdrawals.html", {
        "form": form, "balance": balance, "withdrawals": Withdrawal.objects.filter(organizer=request.user),
    })
