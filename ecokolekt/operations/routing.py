"""Moteur de tournées : distances géodésiques, plus proche voisin, optimisation 2-opt.

Recherche par rayon en deux temps : un filtre rectangulaire en SQL (index latitude / longitude),
puis le calcul exact de distance Haversine en Python.
Pour du routage routier, remplacer `distance_matrix` par un appel à OSRM ou OpenRouteService.
"""
import math

from django.conf import settings

from .models import PickupRequest, PickupStatus

EARTH_RADIUS_M = 6_371_000
EPSILON = 1e-9
METERS_PER_DEGREE_LAT = 111_320


def haversine_m(a, b):
    """Distance en mètres entre deux points (lat, lng)."""
    lat1, lng1 = a
    lat2, lng2 = b
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def distance_matrix(points):
    return [[haversine_m(p, q) for q in points] for p in points]


def tour_length(order, matrix):
    """Longueur d'une tournée fermée (retour au dépôt inclus)."""
    return sum(matrix[order[i]][order[(i + 1) % len(order)]] for i in range(len(order)))


def nearest_neighbour(matrix):
    """Construit une tournée initiale depuis le dépôt (index 0)."""
    unvisited = set(range(1, len(matrix)))
    order = [0]
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: matrix[last][j])
        order.append(nxt)
        unvisited.remove(nxt)
    return order


def two_opt(order, matrix):
    """Améliore la tournée en inversant des segments tant qu'une arête peut être raccourcie."""
    n = len(order)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = order[i - 1], order[i]
                c, d = order[j], order[(j + 1) % n]
                delta = matrix[a][c] + matrix[b][d] - matrix[a][b] - matrix[c][d]
                if delta < -EPSILON:
                    order[i:j + 1] = reversed(order[i:j + 1])
                    improved = True
    return order


def optimize_tour(points):
    """points[0] = dépôt. Retourne (ordre des indices, distance totale en mètres)."""
    matrix = distance_matrix(points)
    order = two_opt(nearest_neighbour(matrix), matrix) if len(points) > 2 else list(range(len(points)))
    return order, round(tour_length(order, matrix))


def bounding_box(lat, lng, radius_m):
    """Rectangle (lat_min, lat_max, lng_min, lng_max) englobant le cercle de rayon donné."""
    dlat = radius_m / METERS_PER_DEGREE_LAT
    dlng = radius_m / (METERS_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 1e-6))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def nearby_pending_pickups(lat, lng, day, radius_m=None):
    """Enlèvements en attente proches de (lat, lng), couvrant le jour demandé, triés par distance."""
    radius_m = radius_m or settings.ROUTE_DEFAULT_RADIUS_M
    lat_min, lat_max, lng_min, lng_max = bounding_box(lat, lng, radius_m)
    candidates = (
        PickupRequest.objects.filter(
            status=PickupStatus.PENDING,
            route__isnull=True,
            window_start__date__lte=day,
            window_end__date__gte=day,
            site__latitude__range=(lat_min, lat_max),
            site__longitude__range=(lng_min, lng_max),
        )
        .select_related("site", "category")
    )
    nearby = []
    for pickup in candidates:
        distance = haversine_m((lat, lng), (pickup.site.latitude, pickup.site.longitude))
        if distance <= radius_m:
            pickup.distance_km = distance / 1000
            nearby.append(pickup)
    return sorted(nearby, key=lambda p: p.distance_km)


def _points(route, pickups):
    depot = (route.origin_latitude, route.origin_longitude)
    return [depot] + [(p.site.latitude, p.site.longitude) for p in pickups]


def assign_stops(route, pickups):
    """Calcule l'ordre optimal et l'applique aux enlèvements de la tournée."""
    order, total = optimize_tour(_points(route, pickups))
    for position, idx in enumerate(order[1:], start=1):
        pickup = pickups[idx - 1]
        pickup.route = route
        pickup.stop_order = position
        pickup.status = PickupStatus.SCHEDULED
        pickup.save(update_fields=["route", "stop_order", "status", "updated_at"])
    route.total_distance_m = total
    route.save(update_fields=["total_distance_m"])
    return route


def replan_route(route):
    """Recalcule la tournée en tenant compte des arrêts encore non collectés (replanification dynamique)."""
    remaining = list(
        route.stops.filter(status=PickupStatus.SCHEDULED).select_related("site").order_by("stop_order")
    )
    if remaining:
        assign_stops(route, remaining)
    return route


def route_stops_ordered(route):
    return route.stops.select_related("site", "category").order_by("stop_order")
