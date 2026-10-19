"""Moteur de routage dynamique.

1. Matrice de coûts (durées/distances) : OSRM `table` si OSRM_URL est défini, sinon haversine × 1,3.
2. Ordre de visite : plus proche voisin puis amélioration 2-opt (chemin ouvert, départ fixe).
3. ETA cumulées, contrôle de capacité du véhicule, géométrie de l'itinéraire (OSRM `route` ou lignes droites).

Appelé : à la demande (/routing/route/optimize/), après chaque scan, et quand une demande est assignée.
Pour de gros volumes (> ~40 arrêts), déléguer à un solveur VRP (OR-Tools, VROOM) derrière la même fonction.
"""
import logging
import math

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction

from waste.models import PickupRequest

from .models import Route, RouteStop

log = logging.getLogger(__name__)
LatLng = tuple  # (lat, lng)


def haversine_m(a: LatLng, b: LatLng) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _osrm_table(points):
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
    r = requests.get(
        f"{settings.OSRM_URL}/table/v1/driving/{coords}", params={"annotations": "duration,distance"}, timeout=8
    )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != "Ok" or any(v is None for row in d["durations"] for v in row):
        raise ValueError("OSRM: matrice incomplète")
    return d["durations"], d["distances"], "osrm"


def _haversine_table(points):
    speed = settings.ROUTING_AVG_SPEED_KMH / 3.6
    dist = [[haversine_m(a, b) * 1.3 for b in points] for a in points]
    return [[v / speed for v in row] for row in dist], dist, "haversine"


def build_matrix(points):
    if settings.OSRM_URL:
        try:
            return _osrm_table(points)
        except Exception as e:  # réseau, OSRM indisponible…
            log.warning("OSRM indisponible, repli haversine: %s", e)
    return _haversine_table(points)


def solve_path(cost):
    """Ordre des nœuds 1..n-1 depuis le nœud 0 (départ), plus proche voisin + 2-opt."""
    n = len(cost)
    left, path, cur = set(range(1, n)), [0], 0
    while left:
        cur = min(left, key=lambda j: cost[cur][j])
        path.append(cur)
        left.remove(cur)

    def total(p):
        return sum(cost[p[i]][p[i + 1]] for i in range(len(p) - 1))

    best, improved = total(path), True
    while improved:
        improved = False
        for i in range(1, len(path) - 1):
            for k in range(i + 1, len(path)):
                cand = path[:i] + path[i : k + 1][::-1] + path[k + 1 :]
                c = total(cand)
                if c < best - 1e-6:
                    path, best, improved = cand, c, True
    return path[1:]


def _geometry(points):
    if settings.OSRM_URL and len(points) > 1:
        try:
            coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
            r = requests.get(
                f"{settings.OSRM_URL}/route/v1/driving/{coords}", params={"overview": "full", "geometries": "geojson"}, timeout=8
            )
            r.raise_for_status()
            return r.json()["routes"][0]["geometry"]
        except Exception as e:
            log.warning("Géométrie OSRM indisponible: %s", e)
    return {"type": "LineString", "coordinates": [[lng, lat] for lat, lng in points]}


@transaction.atomic
def optimize_route(collector, origin: Point | None = None) -> Route:
    profile = getattr(collector, "collector", None)
    pickups = list(
        PickupRequest.objects.select_related("category")
        .filter(collector=collector, status__in=PickupRequest.ACTIVE)
        .order_by("created_at")
    )
    if origin is None and profile and profile.current_location:
        origin = profile.current_location
    if origin is None and pickups:
        origin = pickups[0].location

    route, _ = Route.objects.get_or_create(collector=collector)
    route.stops.all().delete()
    route.origin = origin
    if not pickups or origin is None:
        route.total_distance_m = route.total_duration_s = 0
        route.geometry = None
        route.save()
        return route

    points = [(origin.y, origin.x)] + [(p.location.y, p.location.x) for p in pickups]
    durations, distances, engine = build_matrix(points)
    order = solve_path(durations)

    capacity = (profile.capacity_kg if profile else 10**9)
    load, clock, prev, tot_d = 0, 0, 0, 0
    stops = []
    for seq, node in enumerate(order, start=1):
        p = pickups[node - 1]
        leg_t, leg_d = int(durations[prev][node]), int(distances[prev][node])
        clock += leg_t
        load += float(p.estimated_weight_kg)
        stops.append(
            RouteStop(route=route, pickup=p, sequence=seq, eta_seconds=clock, leg_duration_s=leg_t,
                      leg_distance_m=leg_d, over_capacity=load > capacity)
        )
        clock += settings.ROUTING_SERVICE_TIME_S
        tot_d += leg_d
        prev = node
    RouteStop.objects.bulk_create(stops)

    ordered_points = [points[0]] + [points[n] for n in order]
    route.total_distance_m, route.total_duration_s, route.engine = tot_d, clock, engine
    route.geometry = _geometry(ordered_points)
    route.save()
    return route
