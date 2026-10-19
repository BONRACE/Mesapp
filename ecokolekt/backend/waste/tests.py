from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import CollectorProfile, User

from . import qr
from .models import PickupRequest, WasteCategory

HOME = Point(2.3880, 6.3610, srid=4326)
FAR = Point(2.4400, 6.4200, srid=4326)  # ~8 km


def make_user(phone, role, name="Test", pos=HOME):
    u = User.objects.create_user(phone=phone, full_name=name, role=role, profile_completed=True, is_approved=True, location=pos)
    if role == User.Role.COLLECTOR:
        CollectorProfile.objects.create(user=u, is_on_duty=True, current_location=pos, last_seen=timezone.now(), capacity_kg=100)
    return u


class QRTokenTests(APITestCase):
    def setUp(self):
        self.cat = WasteCategory.objects.create(code="plastique", name="Plastique", points_per_kg=10)
        self.citizen = make_user("+2290196000001", "citizen")
        self.p = PickupRequest.objects.create(citizen=self.citizen, category=self.cat, location=HOME)

    def test_roundtrip(self):
        pid, nonce = qr.parse_token(qr.make_token(self.p))
        self.assertEqual((pid, nonce), (self.p.id, self.p.qr_nonce))

    def test_tampered_token_rejected(self):
        token = qr.make_token(self.p)
        forged = token.replace(self.p.qr_nonce, "deadbeef0000")
        with self.assertRaises(qr.InvalidToken):
            qr.parse_token(forged)
        with self.assertRaises(qr.InvalidToken):
            qr.parse_token("EK1.abc")

    def test_png_is_generated(self):
        self.assertTrue(qr.render_png(qr.make_token(self.p)).startswith(b"\x89PNG"))


class PickupFlowTests(APITestCase):
    def setUp(self):
        self.cat = WasteCategory.objects.create(code="plastique", name="Plastique", points_per_kg=10)
        self.citizen = make_user("+2290196000001", "citizen")
        self.collector = make_user("+2290197123456", "collector", "Koffi", pos=Point(2.3890, 6.3615, srid=4326))
        self.payload = {"category": self.cat.id, "latitude": 6.3610, "longitude": 2.3880, "estimated_weight_kg": "8", "address": "Rue 1"}

    def _create(self):
        self.client.force_authenticate(self.citizen)
        r = self.client.post("/api/waste/pickups/", self.payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return PickupRequest.objects.get(pk=r.data["id"])

    def test_nearby_on_duty_collector_is_auto_assigned(self):
        p = self._create()
        self.assertEqual((p.status, p.collector_id), ("assigned", self.collector.id))

    def test_no_collector_in_radius_stays_pending(self):
        CollectorProfile.objects.update(current_location=FAR)
        self.assertEqual(self._create().status, "pending")

    def test_scan_awards_points_and_qr_is_single_use(self):
        p = self._create()
        token = qr.make_token(p)
        self.client.force_authenticate(self.collector)
        body = {"token": token, "weight_kg": "7.5", "latitude": 6.3611, "longitude": 2.3881}
        r = self.client.post("/api/waste/pickups/scan/", body, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.eco_points, 75)
        replay = self.client.post("/api/waste/pickups/scan/", body, format="json")
        self.assertEqual(replay.status_code, 409)  # rejeu d'un QR photographié

    def test_scan_by_other_collector_forbidden(self):
        p = self._create()
        other = make_user("+2290155123456", "collector", "Autre")
        self.client.force_authenticate(other)
        body = {"token": qr.make_token(p), "weight_kg": "5", "latitude": 6.3611, "longitude": 2.3881}
        r = self.client.post("/api/waste/pickups/scan/", body, format="json")
        self.assertEqual(r.status_code, 403)

    def test_scan_without_gps_refused(self):
        """Sans coordonnées, le contrôle de proximité serait contournable : la requête est rejetée."""
        p = self._create()
        self.client.force_authenticate(self.collector)
        r = self.client.post("/api/waste/pickups/scan/", {"token": qr.make_token(p), "weight_kg": "5"}, format="json")
        self.assertEqual(r.status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.status, "assigned")

    @override_settings(QR_MAX_DISTANCE_M=250)
    def test_scan_too_far_from_household_refused(self):
        p = self._create()
        self.client.force_authenticate(self.collector)
        r = self.client.post("/api/waste/pickups/scan/",
                             {"token": qr.make_token(p), "weight_kg": "5", "latitude": 6.40, "longitude": 2.45}, format="json")
        self.assertEqual(r.status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.status, "assigned")

    def test_forged_token_refused(self):
        self._create()
        self.client.force_authenticate(self.collector)
        body = {"token": "EK1." + "a" * 32 + ".b.c", "weight_kg": "5", "latitude": 6.3611, "longitude": 2.3881}
        r = self.client.post("/api/waste/pickups/scan/", body, format="json")
        self.assertEqual(r.status_code, 400)

    def test_citizen_cannot_see_others_pickups_and_phone_hidden(self):
        p = self._create()
        stranger = make_user("+2290161234567", "citizen", "Voisin")
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.get(f"/api/waste/pickups/{p.id}/").status_code, 404)
        self.client.force_authenticate(self.citizen)
        self.assertIsNone(self.client.get(f"/api/waste/pickups/{p.id}/").data["citizen_phone"])
        self.client.force_authenticate(self.collector)
        self.assertEqual(self.client.get(f"/api/waste/pickups/{p.id}/").data["citizen_phone"], self.citizen.phone)

    def test_qr_only_for_owner_citizen(self):
        p = self._create()
        self.assertEqual(self.client.get(f"/api/waste/pickups/{p.id}/qr/").status_code, 200)
        self.client.force_authenticate(self.collector)
        self.assertEqual(self.client.get(f"/api/waste/pickups/{p.id}/qr/").status_code, 403)

    def test_nearest_collection_points_sorted(self):
        from .models import CollectionPoint

        CollectionPoint.objects.create(name="Loin", location=FAR)
        CollectionPoint.objects.create(name="Près", location=HOME)
        self.client.force_authenticate(self.citizen)
        r = self.client.get("/api/waste/points/?lat=6.361&lng=2.388")
        self.assertEqual([x["name"] for x in r.data], ["Près", "Loin"])
