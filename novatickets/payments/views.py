"""Vues du module de paiement Mobile Money : initiation, webhook, statut / reçu."""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import PaymentForm
from .models import Transaction
from .services import (
    PaymentError, apply_gateway_status, create_transaction, launch_push, sign, signature_is_valid, transaction_receipt_pdf,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------- 2. initiation

def initiate_payment(request):
    """Reçoit le numéro et l'opérateur, crée la transaction PENDING puis déclenche le push USSD."""
    form = PaymentForm(request.POST or None, initial={"amount": request.GET.get("amount", "")})

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            tx = create_transaction(
                user_email=data["user_email"], phone_number=data["phone_number"],
                amount=data["amount"], provider=data["provider"],
            )
        except PaymentError as exc:
            form.add_error(None, str(exc))
        else:
            launch_push(tx, request.build_absolute_uri(reverse("payments:webhook")))
            # Dans tous les cas, on envoie l'utilisateur sur la page de suivi (comme un portail en ligne).
            return redirect("payments:status", pk=tx.pk)

    return render(request, "payments/initiate.html", {"form": form})


# ----------------------------------------------------------------------------- 3. webhook

@csrf_exempt          # appelé par la passerelle (serveur à serveur) : pas de cookie ni de jeton CSRF
@require_POST
def webhook(request):
    """Notification de la passerelle : APPROVED/SUCCESS -> SUCCESS ; refus/annulation -> FAILED.

    Sécurité : la requête n'est acceptée que si l'en-tête X-Signature (HMAC-SHA256 du corps brut,
    avec le secret partagé MOMO_WEBHOOK_SECRET) est valide. Sans cela, n'importe qui pourrait
    « valider » un paiement en appelant cette URL.

    Corps JSON attendu : {"reference": "...", "status": "APPROVED", "transaction_id": "...", "amount": 15000}
    """
    body = request.body
    if not signature_is_valid(body, request.headers.get("X-Signature", "")):
        logger.warning("Webhook refusé : signature invalide (IP %s)", request.META.get("REMOTE_ADDR"))
        return HttpResponse(status=403)

    try:
        payload = json.loads(body.decode())
        reference, raw_status = payload["reference"], payload["status"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"detail": "Corps invalide."}, status=400)

    ts = payload.get("timestamp") if isinstance(payload, dict) else None
    if ts is not None:                                   # anti-rejeu : une notification trop ancienne est refusée
        import time
        try:
            if abs(time.time() - float(ts)) > getattr(settings, "MOMO_WEBHOOK_MAX_AGE", 600):
                logger.warning("Webhook refusé : notification périmée (%s)", reference)
                return JsonResponse({"detail": "Notification périmée."}, status=400)
        except (TypeError, ValueError):
            return JsonResponse({"detail": "Horodatage invalide."}, status=400)

    try:
        tx, changed = apply_gateway_status(
            reference, raw_status,
            gateway_reference=str(payload.get("transaction_id", "")),
            amount=payload.get("amount"), reason=str(payload.get("reason", "")),
        )
    except Transaction.DoesNotExist:
        return JsonResponse({"detail": "Référence inconnue."}, status=404)
    except PaymentError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    # 200 aussi pour un rejeu déjà traité : la passerelle cesse ainsi de renvoyer la notification.
    return JsonResponse({"reference": tx.reference, "status": tx.status, "updated": changed})


# ----------------------------------------------------------------------------- 4. statut / reçu

def _owner_or_404(request, tx):
    """Une transaction liée à une commande / carte / abonnement n'est visible que par son propriétaire connecté
    (l'UUID est non devinable, mais il peut fuiter : historique, capture d'écran, journal de proxy…).
    Un paiement autonome (démo) reste accessible par son seul UUID."""
    owner_id = (tx.order.buyer_id if tx.order_id else tx.business_card.user_id if tx.business_card_id
                else tx.subscription.user_id if tx.subscription_id else None)
    if owner_id is not None and (not request.user.is_authenticated or request.user.id != owner_id):
        raise Http404


def payment_status(request, pk):
    """Page de retour : attente (rafraîchissement auto), reçu si SUCCESS, message + relance si FAILED.

    L'accès repose sur l'UUID de la transaction (non devinable) : le lien peut aussi servir
    d'URL de retour (redirect_url) pour la passerelle.
    """
    tx = get_object_or_404(Transaction, pk=pk)
    _owner_or_404(request, tx)
    return render(request, "payments/status.html", {
        "tx": tx,
        "refresh_seconds": 4 if tx.is_pending else 0,
        "simulation": getattr(settings, "MOMO_GATEWAY_MODE", "simulation") == "simulation" and settings.DEBUG,
    })


def payment_status_json(request, pk):
    """Même information en JSON, pour un éventuel rafraîchissement AJAX."""
    tx = get_object_or_404(Transaction, pk=pk)
    _owner_or_404(request, tx)
    return JsonResponse({"reference": tx.reference, "status": tx.status})


def receipt_pdf(request, pk):
    """Reçu PDF téléchargeable ; seulement une fois le paiement réussi (accès par UUID non devinable)."""
    tx = get_object_or_404(Transaction, pk=pk, status=Transaction.Status.SUCCESS)
    _owner_or_404(request, tx)
    resp = HttpResponse(transaction_receipt_pdf(tx), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="recu-{tx.reference}.pdf"'
    return resp


# ----------------------------------------------------------------------------- simulation (DEBUG)

@require_POST
def simulate_callback(request, pk):
    """Outil de développement : joue la notification de la passerelle (approuvée ou refusée).

    Désactivé hors simulation/DEBUG. Passe par le même code que le vrai webhook, signature comprise.
    """
    if not (settings.DEBUG and getattr(settings, "MOMO_GATEWAY_MODE", "simulation") == "simulation"):
        raise Http404
    tx = get_object_or_404(Transaction, pk=pk)
    outcome = "APPROVED" if request.POST.get("outcome") == "approve" else "DECLINED"
    payload = json.dumps({"reference": tx.reference, "status": outcome, "transaction_id": tx.gateway_reference,
                          "amount": int(tx.amount)}).encode()
    response = _call_webhook(payload)
    if response.status_code != 200:
        messages.error(request, f"Webhook simulé refusé ({response.status_code}).")
    return redirect("payments:status", pk=tx.pk)


def _call_webhook(payload):
    """Appelle la vue webhook en interne avec une requête signée (sans passer par le réseau)."""
    from django.test import RequestFactory
    fake = RequestFactory().post(reverse("payments:webhook"), data=payload, content_type="application/json",
                                 HTTP_X_SIGNATURE=sign(payload))
    return webhook(fake)
