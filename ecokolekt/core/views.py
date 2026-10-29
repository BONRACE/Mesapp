from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Role
from marketplace.models import Listing, Order
from operations.models import PickupRequest, PickupStatus, Route
from traceability.models import WasteBatch


def landing(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    stats = {
        "kg_collected": PickupRequest.objects.filter(status=PickupStatus.COLLECTED)
                        .aggregate(total=Sum("actual_kg"))["total"] or 0,
        "batches": WasteBatch.objects.count(),
        "listings": Listing.objects.filter(status=Listing.Status.ACTIVE).count(),
    }
    return render(request, "core/landing.html", {"stats": stats})


@login_required
def dashboard(request):
    user = request.user
    if not user.is_onboarded:
        return redirect("accounts:onboarding")
    builders = {
        Role.PRODUCER: _producer_context,
        Role.COLLECTOR: _collector_context,
        Role.RECYCLER: _recycler_context,
    }
    context = builders[user.role](user)
    template = f"core/dashboard_{user.role}.html"
    return render(request, template, context)


def _producer_context(user):
    pickups = PickupRequest.objects.filter(producer=user).select_related("site", "category")
    return {
        "pickups": pickups[:10],
        "kg_collected": pickups.filter(status=PickupStatus.COLLECTED).aggregate(t=Sum("actual_kg"))["t"] or 0,
        "pending_count": pickups.filter(status__in=[PickupStatus.PENDING, PickupStatus.SCHEDULED]).count(),
        "batches": WasteBatch.objects.filter(producer=user).select_related("category")[:6],
    }


def _collector_context(user):
    today = timezone.localdate()
    routes = Route.objects.filter(collector=user, planned_for__gte=today).order_by("planned_for")
    stops = PickupRequest.objects.filter(collector=user)
    return {
        "routes": routes[:5],
        "to_plan_count": stops.filter(status=PickupStatus.SCHEDULED, route__isnull=True).count(),
        "in_progress": stops.filter(status=PickupStatus.SCHEDULED, route__isnull=False).count(),
        "collected_count": stops.filter(status=PickupStatus.COLLECTED).count(),
        "kg_collected": stops.filter(status=PickupStatus.COLLECTED).aggregate(t=Sum("actual_kg"))["t"] or 0,
    }


def _recycler_context(user):
    incoming = WasteBatch.objects.filter(holder=user).select_related("category", "producer")
    sales = Order.objects.filter(listing__seller=user, status=Order.Status.PAID)
    return {
        "incoming": incoming[:8],
        "incoming_count": incoming.count(),
        "listings_count": Listing.objects.filter(seller=user, status=Listing.Status.ACTIVE).count(),
        "revenue_xof": sales.aggregate(t=Sum("seller_payout_xof"))["t"] or 0,
        "orders_count": sales.count(),
        "recent_orders": sales.select_related("listing", "buyer")[:5],
        "stock_summary": Listing.objects.filter(seller=user).aggregate(
            kg=Sum("available_kg"), offers=Count("id", filter=Q(status=Listing.Status.ACTIVE))
        ),
    }
