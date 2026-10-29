from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from traceability.services import create_batch_from_pickup

from .forms import ActualWeightForm, PickupRequestForm, RoutePlanForm, SiteForm
from .models import PickupRequest, PickupStatus, Route, Site
from .routing import assign_stops, nearby_pending_pickups, replan_route, route_stops_ordered


def _radius_m(raw, default_km=10):
    try:
        km = int(raw)
    except (TypeError, ValueError):
        km = default_km
    return max(1, min(km, 100)) * 1000


@login_required
def site_list(request):
    sites = Site.objects.filter(owner=request.user).prefetch_related("accepted_categories")
    return render(request, "operations/site_list.html", {"sites": sites})


@login_required
def site_create(request):
    form = SiteForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        site = form.save(commit=False)
        site.owner = request.user
        site.save()
        form.save_m2m()
        messages.success(request, "Site enregistré.")
        return redirect("operations:site_list")
    return render(request, "operations/site_form.html", {"form": form})


@role_required("producer")
def pickup_create(request):
    form = PickupRequestForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        pickup = form.save(commit=False)
        pickup.producer = request.user
        pickup.save()
        messages.success(request, "Demande d'enlèvement envoyée.")
        return redirect("core:dashboard")
    return render(request, "operations/pickup_form.html", {"form": form})


@role_required("collector")
def available_pickups(request):
    """Enlèvements en attente proches du point de départ, et enlèvements acceptés à planifier."""
    depots = Site.objects.filter(owner=request.user, kind=Site.Kind.COLLECTION)
    depot = depots.filter(pk=request.GET.get("depot")).first() or depots.first()
    day = request.GET.get("day") or timezone.localdate().isoformat()
    radius_m = _radius_m(request.GET.get("radius_km"))
    nearby = nearby_pending_pickups(depot.latitude, depot.longitude, day, radius_m) if depot else []
    to_plan = PickupRequest.objects.filter(
        collector=request.user, status=PickupStatus.SCHEDULED, route__isnull=True,
    ).select_related("site", "category")
    plan_form = RoutePlanForm(user=request.user, initial={"planned_for": day, "depot": depot})
    return render(request, "operations/available_pickups.html", {
        "nearby": nearby,
        "to_plan": to_plan,
        "depots": depots,
        "depot": depot,
        "day": day,
        "radius_km": radius_m // 1000,
        "plan_form": plan_form,
    })


@role_required("collector")
@require_POST
def accept_pickup(request, pk):
    with transaction.atomic():
        pickup = get_object_or_404(PickupRequest.objects.select_for_update(), pk=pk)
        if pickup.status != PickupStatus.PENDING:
            messages.error(request, "Cet enlèvement n'est plus disponible.")
        else:
            pickup.collector = request.user
            pickup.status = PickupStatus.SCHEDULED
            pickup.save(update_fields=["collector", "status", "updated_at"])
            messages.success(request, "Enlèvement accepté. Ajoutez-le à une tournée.")
    return redirect("operations:available_pickups")


@role_required("collector")
@require_POST
def plan_route(request):
    """Crée une tournée optimisée à partir des enlèvements acceptés et sélectionnés."""
    form = RoutePlanForm(request.POST, user=request.user)
    selected = request.POST.getlist("pickups")
    if not form.is_valid() or not selected:
        messages.error(request, "Choisissez un point de départ, une date et au moins un enlèvement.")
        return redirect("operations:available_pickups")
    depot = form.cleaned_data["depot"]
    pickups = list(
        PickupRequest.objects.filter(
            pk__in=selected, collector=request.user,
            status=PickupStatus.SCHEDULED, route__isnull=True,
        ).select_related("site")
    )
    if not pickups:
        messages.error(request, "Aucun enlèvement valide sélectionné.")
        return redirect("operations:available_pickups")
    route = Route.objects.create(
        collector=request.user,
        planned_for=form.cleaned_data["planned_for"],
        origin_latitude=depot.latitude,
        origin_longitude=depot.longitude,
    )
    assign_stops(route, pickups)
    messages.success(request, f"Tournée optimisée : {len(pickups)} arrêt(s).")
    return redirect("operations:route_detail", pk=route.pk)


@role_required("collector")
def route_detail(request, pk):
    route = get_object_or_404(Route, pk=pk, collector=request.user)
    stops = route_stops_ordered(route)
    return render(request, "operations/route_detail.html", {
        "route": route, "stops": stops, "weight_form": ActualWeightForm(),
    })


@role_required("collector")
@require_POST
def route_replan(request, pk):
    route = get_object_or_404(Route, pk=pk, collector=request.user)
    replan_route(route)
    messages.success(request, "Tournée recalculée avec les arrêts restants.")
    return redirect("operations:route_detail", pk=route.pk)


@role_required("collector")
@require_POST
def stop_collected(request, pk):
    """Valide une collecte : poids réel, statut COLLECTED et création du lot tracé (QR)."""
    pickup = get_object_or_404(PickupRequest, pk=pk, collector=request.user, status=PickupStatus.SCHEDULED)
    form = ActualWeightForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Poids invalide.")
        return redirect("operations:route_detail", pk=pickup.route_id)
    with transaction.atomic():
        pickup.actual_kg = form.cleaned_data["actual_kg"]
        pickup.status = PickupStatus.COLLECTED
        pickup.save(update_fields=["actual_kg", "status", "updated_at"])
        batch = create_batch_from_pickup(pickup, actor=request.user)
    messages.success(request, f"Collecte validée. Lot {batch.code} créé.")
    return redirect("operations:route_detail", pk=pickup.route_id)
