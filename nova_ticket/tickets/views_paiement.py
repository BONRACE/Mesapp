"""
Vues liées au paiement FedaPay :

- `paiement_retour` : page sur laquelle FedaPay redirige le spectateur après son passage sur la
  page de paiement hébergée (succès, échec ou abandon). Purement informative pour l'internaute —
  ce n'est PAS elle qui valide le billet (un utilisateur pourrait très bien ne jamais y revenir,
  ou la rejouer manuellement). Elle se contente d'afficher l'état actuel du billet.

- `fedapay_webhook` : source de vérité. FedaPay y notifie l'issue réelle de la transaction
  (`transaction.approved`, `transaction.declined`, `transaction.canceled`). C'est cette vue,
  et uniquement elle, qui valide le billet, calcule/enregistre la commission et déclenche
  l'envoi du reçu.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Ticket
from .emails import envoyer_recu_billet
from . import fedapay_client
from .fedapay_client import WebhookSignatureError, FedaPayError

logger = logging.getLogger(__name__)


@login_required
def paiement_retour(request):
    """Page de retour après le paiement (callback_url). Affiche l'état actuel du billet —
    le webhook a généralement déjà eu le temps de le valider avant que l'utilisateur revienne,
    mais ce n'est pas garanti : le gabarit invite à rafraîchir si le paiement est encore visible
    comme "en attente"."""
    ticket_id = request.GET.get("ticket")
    ticket = get_object_or_404(Ticket, pk=ticket_id, spectateur=request.user)
    return render(request, "tickets/paiement_retour.html", {"ticket": ticket})


def _finaliser_paiement_approuve(transaction_data):
    """Valide le billet OU l'abonnement Pro correspondant à une transaction FedaPay approuvée
    (idempotent : si déjà traité — webhook rejoué — on ne fait rien de plus)."""
    transaction_id = str(transaction_data.get("id"))

    try:
        ticket = Ticket.objects.select_related("ticket_type", "spectateur").get(
            fedapay_transaction_id=transaction_id
        )
    except Ticket.DoesNotExist:
        _finaliser_abonnement_pro(transaction_id)
        return

    if ticket.statut != Ticket.Statut.EN_ATTENTE:
        return  # déjà traité (webhook redélivré) — rien à refaire, on ne double-compte rien

    ticket.statut = Ticket.Statut.VALIDE
    ticket.save(update_fields=["statut"])

    ticket_type = ticket.ticket_type
    ticket_type.quantite_vendue += 1
    ticket_type.save(update_fields=["quantite_vendue"])

    envoyer_recu_billet(ticket)


def _finaliser_abonnement_pro(transaction_id):
    """Active (ou renouvelle) le plan Pro d'un organisateur suite au paiement de son abonnement.
    Appelé quand la transaction approuvée ne correspond à aucun billet (voir ci-dessus)."""
    from datetime import timedelta
    from django.conf import settings
    from accounts.models import PlanAbonnement

    try:
        plan = PlanAbonnement.objects.get(fedapay_transaction_id=transaction_id)
    except PlanAbonnement.DoesNotExist:
        logger.warning("Webhook FedaPay : transaction %s introuvable (ni billet, ni abonnement).",
                        transaction_id)
        return

    if plan.est_pro_actif():
        return  # déjà activé (webhook rejoué) — on ne prolonge pas une seconde fois par erreur

    maintenant = timezone.now()
    depart = plan.date_expiration if (plan.date_expiration and plan.date_expiration > maintenant) else maintenant
    plan.plan = PlanAbonnement.Plan.PRO
    plan.statut = PlanAbonnement.Statut.ACTIF
    plan.date_expiration = depart + timedelta(days=settings.PLAN_PRO_DUREE_JOURS)
    plan.save(update_fields=["plan", "statut", "date_expiration"])


def _marquer_paiement_echoue(transaction_data):
    transaction_id = str(transaction_data.get("id"))
    Ticket.objects.filter(
        fedapay_transaction_id=transaction_id, statut=Ticket.Statut.EN_ATTENTE
    ).update(statut=Ticket.Statut.ANNULE)


@csrf_exempt
@require_POST
def fedapay_webhook(request):
    """Point d'entrée webhook FedaPay — URL à renseigner dans le dashboard FedaPay
    (Développeurs > Webhooks), événements `transaction.approved` au minimum
    (idéalement aussi `transaction.declined` et `transaction.canceled`)."""
    from django.conf import settings

    signature = request.headers.get("X-FEDAPAY-SIGNATURE", "")
    try:
        event = fedapay_client.verify_webhook_signature(
            request.body, signature, settings.FEDAPAY_WEBHOOK_SECRET
        )
    except WebhookSignatureError as exc:
        logger.warning("Webhook FedaPay rejeté : signature invalide (%s).", exc)
        return JsonResponse({"error": "invalid signature"}, status=400)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid payload"}, status=400)

    event_name = event.get("name") or event.get("event")
    data = event.get("data", event.get("entity", {}))

    # Vérification supplémentaire côté serveur : on relit la transaction directement auprès de
    # l'API FedaPay plutôt que de faire une confiance aveugle au contenu du webhook. Best-effort :
    # si l'appel échoue (API momentanément indisponible), on continue sur la foi du webhook signé.
    transaction_id = data.get("id")
    if transaction_id:
        try:
            data = fedapay_client.recuperer_transaction(transaction_id)
        except FedaPayError as exc:
            logger.warning("Relecture API de la transaction %s impossible (%s) — "
                            "traitement sur la base du seul webhook signé.", transaction_id, exc)

    if event_name == "transaction.approved":
        _finaliser_paiement_approuve(data)
    elif event_name in ("transaction.declined", "transaction.canceled"):
        _marquer_paiement_echoue(data)
    else:
        logger.info("Webhook FedaPay ignoré (événement non géré) : %s", event_name)

    # Toujours répondre 2xx une fois la signature validée, y compris pour un événement ignoré —
    # sans quoi FedaPay réessaiera inutilement (voir doc : "Respond Quickly with a 2xx Status").
    return JsonResponse({"received": True})
