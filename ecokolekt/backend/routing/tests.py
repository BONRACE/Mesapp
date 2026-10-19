from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from waste.models import PickupRequest, WasteCategory
from waste.tests import HOME, make_user

from .services import haversine_m, solve_path


class SolverTests(APITestCase):
    def test_haversine_cotonou_known_distance(self):
        # Cadjèhoun -> Dantokpa ≈ 5,7 km à vol d'oiseau
        d = haversine_m((6.3600, 2.3850), (6.3665, 2.4350))
        self.assertTrue(5000 < d < 6200, d)

    def test_solver_visits_points_in_line_order(self):
        xs = [0, 5, 1, 4, 2, 3]  # départ en 0, puis points mélangés sur une droite
        cost = [[abs(a - b) for b in xs] for a in xs]
        order = solve_path(cost)
        self.assertEqual([xs[i] for i in order], [1, 2, 3, 4, 5])

    def test_two_opt_fixes_a_crossing(self):
        # Plus proche voisin seul donne un croisement sur ce jeu ; 2-opt doit atteindre l'optimum.
        pts = [(0, 0), (0, 10), (10, 0), (10, 10), (5, 5)]
        cost = [[((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for b in pts] for a in pts]
        order = solve_path(cost)
        tour = sum(cost[a][b] for a, b in zip([0] + order, order))
        import itertools

        best = min(sum(cost[a][b] for a, b in zip((0,) + p, p)) for p in itertools.permutations(range(1, 5)))
        self.assertAlmostEqual(tour, best, places=6)


class RouteApiTests(APITestCase):
    def setUp(self):
        self.cat = WasteCategory.objects.create(code="p", name="P", points_per_kg=1)
        self.collector = make_user("+2290197123456", "collector", "Koffi")
        self.citizen = make_user("+2290196000001", "citizen")
        for lat, lng, kg in [(6.3700, 2.3900, 40), (6.3620, 2.3885, 40), (6.3650, 2.3890, 40)]:
            PickupRequest.objects.create(citizen=self.citizen, collector=self.collector, category=self.cat, status="assigned",
                                         location=Point(lng, lat, srid=4326), estimated_weight_kg=kg)

    def test_route_orders_stops_nearest_first_and_flags_capacity(self):
        self.client.force_authenticate(self.collector)
        r = self.client.get("/api/routing/route/")
        self.assertEqual(r.status_code, 200)
        lats = [s["pickup"]["lat"] for s in r.data["stops"]]
        self.assertEqual(lats, sorted(lats))  # on remonte du sud au nord depuis HOME (6.361)
        self.assertEqual([s["sequence"] for s in r.data["stops"]], [1, 2, 3])
        etas = [s["eta_seconds"] for s in r.data["stops"]]
        self.assertEqual(etas, sorted(etas))
        # capacité 100 kg, 3 × 40 kg : le 3e arrêt dépasse
        self.assertEqual([s["over_capacity"] for s in r.data["stops"]], [False, False, True])
        self.assertEqual(r.data["geometry"]["type"], "LineString")

    def test_route_recomputes_when_a_stop_disappears(self):
        self.client.force_authenticate(self.collector)
        PickupRequest.objects.filter(location__distance_lte=(Point(2.3885, 6.3620, srid=4326), 50)).update(status="collected")
        r = self.client.get("/api/routing/route/")
        self.assertEqual(len(r.data["stops"]), 2)

    def test_empty_route(self):
        PickupRequest.objects.update(status="collected")
        self.client.force_authenticate(self.collector)
        r = self.client.get("/api/routing/route/")
        self.assertEqual((r.data["stops"], r.data["total_distance_m"]), ([], 0))

    def test_citizen_cannot_use_route_and_admin_map_is_admin_only(self):
        self.client.force_authenticate(self.citizen)
        self.assertEqual(self.client.get("/api/routing/route/").status_code, 403)
        self.assertEqual(self.client.get("/api/routing/collectors/live/").status_code, 403)
