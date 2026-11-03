"""Statistiques organisateur : ventes, revenus, remplissage, affluence des scans.

Tout est calculé en base (agrégations) puis renvoyé en un seul dictionnaire sérialisable,
utilisé à la fois par la page et par l'endpoint JSON de rafraîchissement.
"""
from datetime import datetime, time, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order, Ticket
from scanner.models import ScanLog


def _pct(part, whole):
    return round(part * 100 / whole, 1) if whole else 0


def build_stats(user, event=None, days=30):
    """Statistiques de tous les événements de `user`, ou d'un seul si `event` est fourni."""
    today = timezone.localdate()
    events = Event.objects.filter(organizer=user)
    if event is not None:
        events = events.filter(pk=event.pk)

    orders = Order.objects.filter(event__in=events, status=Order.Status.PAID)
    agg = orders.aggregate(tickets=Sum("quantity"), orders=Count("id"), gross=Sum("total"),
                           commission=Sum("commission"), net=Sum("organizer_amount"))
    sold = agg["tickets"] or 0
    stock = TicketType.objects.filter(event__in=events).aggregate(s=Sum("stock"))["s"] or 0
    checked_in = Ticket.objects.filter(order__in=orders, used_at__isnull=False).count()
    gross, net = agg["gross"] or 0, agg["net"] or 0

    # --- ventes par jour (série complète, jours sans vente = 0)
    start = today - timedelta(days=days - 1)
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    per_day = {r["d"]: r for r in orders.filter(paid_at__gte=start_dt).annotate(d=TruncDate("paid_at"))
               .values("d").annotate(t=Sum("quantity"), r=Sum("organizer_amount"))}
    daily = []
    for i in range(days):
        d = start + timedelta(days=i)
        row = per_day.get(d)
        daily.append({"label": d.strftime("%d/%m"), "tickets": (row or {}).get("t") or 0, "revenue": (row or {}).get("r") or 0})

    # --- remplissage par type de ticket
    by_type_rows = {r["ticket_type"]: r for r in orders.values("ticket_type").annotate(q=Sum("quantity"), n=Sum("organizer_amount"))}
    by_type = []
    for tt in TicketType.objects.filter(event__in=events).select_related("event").order_by("event__start_date", "price"):
        row = by_type_rows.get(tt.id) or {}
        qty = row.get("q") or 0
        by_type.append({
            "name": tt.name, "event": "" if event is not None else tt.event.name,
            "price": tt.price, "sold": qty, "stock": tt.stock, "fill": _pct(qty, tt.stock), "revenue": row.get("n") or 0,
        })

    # --- scans : résultats + affluence par heure
    scans = ScanLog.objects.filter(event__in=events)
    sc = scans.aggregate(valid=Count("id", filter=Q(result="valid")), duplicate=Count("id", filter=Q(result="duplicate")),
                         refused=Count("id", filter=Q(result__in=["invalid", "wrong_event"])))
    valid = scans.filter(result="valid")
    hourly, peak = [], None
    last, first = valid.order_by("-scanned_at").first(), valid.order_by("scanned_at").first()
    if last:
        end = timezone.localtime(last.scanned_at).replace(minute=0, second=0, microsecond=0)
        begin = max(timezone.localtime(first.scanned_at).replace(minute=0, second=0, microsecond=0), end - timedelta(hours=23))
        counts = {timezone.localtime(r["h"]): r["n"] for r in valid.filter(scanned_at__gte=begin)
                  .annotate(h=TruncHour("scanned_at")).values("h").annotate(n=Count("id"))}
        multi_day = begin.date() != end.date()
        h = begin
        while h <= end:
            hourly.append({"label": h.strftime("%d/%m %Hh" if multi_day else "%Hh"), "count": counts.get(h, 0)})
            h += timedelta(hours=1)
        peak = max(hourly, key=lambda x: x["count"]) if hourly else None

    recent_sales = [{
        "when": timezone.localtime(o.paid_at).strftime("%d/%m %H:%M"), "buyer": o.buyer.display_name,
        "event": o.event.name, "what": f"{o.quantity} × {o.ticket_type.name}", "net": o.organizer_amount,
    } for o in orders.select_related("buyer", "event", "ticket_type").order_by("-paid_at")[:8]]
    recent_scans = [{
        "when": timezone.localtime(s.scanned_at).strftime("%d/%m %H:%M"), "result": s.result, "label": s.get_result_display(),
        "who": s.ticket.order.buyer.ticket_name if s.ticket else (s.code or "—")[:24],
    } for s in scans.select_related("ticket__order__buyer").order_by("-scanned_at")[:8]]

    return {
        "kpi": {
            "tickets": sold, "orders": agg["orders"] or 0, "gross": gross, "commission": agg["commission"] or 0, "net": net,
            "stock": stock, "fill_rate": _pct(sold, stock), "checked_in": checked_in,
            "attendance_rate": _pct(checked_in, sold), "avg_order": round(gross / agg["orders"]) if agg["orders"] else 0,
        },
        "daily": daily, "by_type": by_type, "scans": {**sc, "hourly": hourly, "peak": peak},
        "recent_sales": recent_sales, "recent_scans": recent_scans,
        "updated_at": timezone.localtime().strftime("%H:%M:%S"),
    }
