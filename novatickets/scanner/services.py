"""Contrôle d'entrée : lecture d'un QR code, validation atomique du billet, journalisation."""
import re

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from orders.models import Order, Ticket

from .models import ScanLog

# Le QR contient l'URL de vérification (…/verification/TK-XXXXXXXXXX/) ; on accepte aussi la référence seule.
REF_RE = re.compile(r"TK-[A-Z2-9]{10}")


def extract_reference(code):
    m = REF_RE.search((code or "").strip().upper())
    return m.group(0) if m else ""


def event_stats(event):
    """Billets vendus et déjà contrôlés pour un événement."""
    agg = Ticket.objects.filter(order__event=event, order__status=Order.Status.PAID).aggregate(
        total=Count("id"), checked_in=Count("id", filter=Q(used_at__isnull=False)))
    total, done = agg["total"] or 0, agg["checked_in"] or 0
    return {"total": total, "checked_in": done, "remaining": total - done}


def _ticket_info(ticket):
    holder = ticket.order.buyer
    return {
        "reference": ticket.reference,
        "holder": holder.ticket_name,
        "type": ticket.order.ticket_type.name,
        "photo": holder.photo.url if holder.photo else "",
        "initials": holder.initials,
    }


def check_in(*, user, event, code, source=ScanLog.Source.CAMERA):
    """Valide un billet pour `event`. Renvoie un dict JSON-able {result, message, ticket?}.

    Atomique : deux scans simultanés du même billet ne peuvent pas tous deux réussir.
    Un billet d'un autre organisateur est traité comme « invalide » (on ne révèle rien sur lui).
    """
    reference = extract_reference(code)
    ticket = None
    result, message, info = ScanLog.Result.INVALID, "Billet inconnu ou non payé.", None

    if reference:
        with transaction.atomic():
            ticket = (Ticket.objects.select_for_update(of=("self",))
                      .select_related("order__event__organizer", "order__buyer", "order__ticket_type")
                      .filter(reference=reference, order__status=Order.Status.PAID).first())
            if ticket and ticket.order.event.organizer_id == user.id:
                info = _ticket_info(ticket)
                if ticket.order.event_id != event.id:
                    result = ScanLog.Result.WRONG_EVENT
                    message = f"Ce billet est pour « {ticket.order.event.name} », pas pour cet événement."
                elif ticket.used_at:
                    local = timezone.localtime(ticket.used_at)
                    result = ScanLog.Result.DUPLICATE
                    message = f"Billet déjà utilisé le {local:%d/%m à %H:%M}."
                else:
                    ticket.used_at = timezone.now()
                    ticket.save(update_fields=["used_at"])
                    result, message = ScanLog.Result.VALID, "Entrée validée."
            else:
                ticket = None  # inexistant, impayé ou d'un autre organisateur : aucune fuite d'information

    ScanLog.objects.create(event=event, ticket=ticket, scanned_by=user, code=(code or "")[:200], result=result, source=source)
    return {"result": result.value, "message": message, "ticket": info, "stats": event_stats(event)}
