import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from marketplace.models import Listing, Order
from marketplace.services import OutOfStock, cancel_order, create_order, mark_paid
from operations.models import PickupRequest, PickupStatus, Route, Site, WasteCategory
from operations.routing import assign_stops, nearby_pending_pickups
from traceability.models import EventType, TrackingEvent
from traceability.services import (
    batch_from_token, create_batch_from_pickup, record_event, sign_batch_token, verify_chain,
)

CENTRE = (6.3703, 2.3912)          # Cotonou
NEAR = (6.3803, 2.4012)            # ~1,5 km
FAR = (6.8703, 2.3912)             # ~55 km


def make_user(phone, role):
    return User.objects.create_user(phone_number=phone, role=role, is_onboarded=True)


def make_site(owner, kind, point, name="Site"):
    return Site.objects.create(owner=owner, kind=kind, name=name, latitude=point[0], longitude=point[1])


def make_pickup(producer, site, category):
    now = timezone.now()
    return PickupRequest.objects.create(
        producer=producer, site=site, category=category, estimated_kg=Decimal("20"),
        window_start=now - timedelta(days=1), window_end=now + timedelta(days=1),
    )


class OTPFlowTests(TestCase):
    def test_login_then_verify_then_onboarding(self):
        client = Client()
        sent = []
        fake_sms = mock.Mock()
        fake_sms.send.side_effect = lambda phone, message: sent.append(message)
        with mock.patch("accounts.otp.get_sms_backend", return_value=fake_sms):
            resp = client.post(reverse("accounts:login"), {"phone_number": "+22997000000"})
        self.assertRedirects(resp, reverse("accounts:verify"))
        code = re.search(r"\d{6}", sent[-1]).group(0)

        wrong = "000000" if code != "000000" else "111111"
        resp = client.post(reverse("accounts:verify"), {"code": wrong})
        self.assertEqual(resp.status_code, 200)

        resp = client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(resp, reverse("accounts:onboarding"))
        self.assertTrue(User.objects.filter(phone_number="+22997000000", is_phone_verified=True).exists())

    def test_old_code_is_refused_once_a_new_one_is_issued(self):
        client = Client()
        sent = []
        fake_sms = mock.Mock()
        fake_sms.send.side_effect = lambda phone, message: sent.append(message)
        with mock.patch("accounts.otp.get_sms_backend", return_value=fake_sms):
            client.post(reverse("accounts:login"), {"phone_number": "+22997111111"})
        code = re.search(r"\d{6}", sent[-1]).group(0)
        client.post(reverse("accounts:verify"), {"code": code})
        client.logout()
        with mock.patch("accounts.otp.get_sms_backend", return_value=fake_sms):
            client.post(reverse("accounts:login"), {"phone_number": "+22997111111"})
        resp = client.post(reverse("accounts:verify"), {"code": code})
        self.assertEqual(resp.status_code, 200)


class RoutingTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.category = WasteCategory.objects.create(code="plastic", label="Plastique PET")
        self.producer = make_user("+22997000001", "producer")
        self.collector = make_user("+22997000002", "collector")
        self.depot = make_site(self.collector, Site.Kind.COLLECTION, CENTRE, "Dépôt")

    def test_nearby_respects_radius_and_sorts_by_distance(self):
        near_site = make_site(self.producer, Site.Kind.PRODUCTION, NEAR, "Proche")
        far_site = make_site(self.producer, Site.Kind.PRODUCTION, FAR, "Lointain")
        near = make_pickup(self.producer, near_site, self.category)
        make_pickup(self.producer, far_site, self.category)

        result = nearby_pending_pickups(self.depot.latitude, self.depot.longitude, self.today.isoformat(), 10_000)
        self.assertEqual([p.pk for p in result], [near.pk])
        self.assertLess(result[0].distance_km, 10)

    def test_route_orders_stops_and_stores_distance(self):
        pickups = []
        for i, point in enumerate([(6.40, 2.41), (6.36, 2.44), (6.38, 2.37)]):
            site = make_site(self.producer, Site.Kind.PRODUCTION, point, f"Site {i}")
            pickup = make_pickup(self.producer, site, self.category)
            pickup.collector = self.collector
            pickup.status = PickupStatus.SCHEDULED
            pickup.save()
            pickups.append(pickup)

        route = Route.objects.create(
            collector=self.collector, planned_for=self.today,
            origin_latitude=self.depot.latitude, origin_longitude=self.depot.longitude,
        )
        assign_stops(route, pickups)

        route.refresh_from_db()
        orders = sorted(p.stop_order for p in route.stops.all())
        self.assertEqual(orders, [1, 2, 3])
        self.assertGreater(route.total_distance_m, 0)
        self.assertTrue(all(p.status == PickupStatus.SCHEDULED for p in route.stops.all()))


class TraceabilityTests(TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(code="cardboard", label="Carton")
        self.producer = make_user("+22997000003", "producer")
        self.collector = make_user("+22997000004", "collector")
        self.recycler = make_user("+22997000005", "recycler")
        site = make_site(self.producer, Site.Kind.PRODUCTION, NEAR, "Atelier")
        self.pickup = make_pickup(self.producer, site, self.category)
        self.pickup.actual_kg = Decimal("18.50")
        self.pickup.collector = self.collector
        self.pickup.save()
        self.batch = create_batch_from_pickup(self.pickup, self.collector)

    def test_new_batch_has_valid_chain(self):
        self.assertEqual(self.batch.events.count(), 2)
        self.assertTrue(verify_chain(self.batch))

    def test_tampered_event_is_detected(self):
        event = self.batch.events.first()
        TrackingEvent.objects.filter(pk=event.pk).update(note="falsifié")
        self.assertFalse(verify_chain(self.batch))

    def test_qr_token_roundtrip_and_forgery(self):
        token = sign_batch_token(self.batch)
        self.assertEqual(batch_from_token(token), self.batch)
        forged = token[:-1] + ("A" if token[-1] != "A" else "B")
        self.assertIsNone(batch_from_token(forged))

    def test_recipient_receives_batch(self):
        record_event(self.batch, self.recycler, EventType.RECEIVED, note="Réception")
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.holder, self.recycler)
        self.assertEqual(self.batch.status, "at_center")
        self.assertTrue(verify_chain(self.batch))


class MarketplaceTests(TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(code="pet", label="PET")
        self.seller = make_user("+22997000006", "recycler")
        self.buyer = make_user("+22997000007", "recycler")
        self.listing = Listing.objects.create(
            seller=self.seller, category=self.category, title="Paillettes PET",
            available_kg=Decimal("100"), price_per_kg_xof=500,
        )

    def test_order_reserves_stock_and_computes_commission(self):
        order = create_order(self.buyer, self.listing.pk, Decimal("40"))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.available_kg, Decimal("60"))
        self.assertEqual(order.subtotal_xof, 20_000)
        self.assertEqual(order.commission_xof, 1_000)
        self.assertEqual(order.seller_payout_xof, 19_000)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)

    def test_out_of_stock_is_refused(self):
        with self.assertRaises(OutOfStock):
            create_order(self.buyer, self.listing.pk, Decimal("200"))

    def test_seller_cannot_buy_own_listing(self):
        with self.assertRaises(ValueError):
            create_order(self.seller, self.listing.pk, Decimal("5"))

    def test_full_purchase_sells_out_then_cancel_restores(self):
        order = create_order(self.buyer, self.listing.pk, Decimal("100"))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.SOLD_OUT)
        cancel_order(order)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.available_kg, Decimal("100"))
        self.assertEqual(self.listing.status, Listing.Status.ACTIVE)

    def test_mark_paid_is_idempotent(self):
        order = create_order(self.buyer, self.listing.pk, Decimal("10"))
        mark_paid(order)
        first_paid_at = Order.objects.get(pk=order.pk).paid_at
        mark_paid(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.paid_at, first_paid_at)


class PagesSmokeTests(TestCase):
    """Vérifie que chaque tableau de bord et les pages principales se rendent sans erreur."""

    def test_landing_renders(self):
        self.assertEqual(Client().get(reverse("core:landing")).status_code, 200)

    def test_each_role_dashboard_renders(self):
        for index, role in enumerate(["producer", "collector", "recycler"]):
            user = make_user(f"+22997001{index:04d}", role)
            client = Client()
            client.force_login(user)
            self.assertEqual(client.get(reverse("core:dashboard")).status_code, 200, role)

    def test_marketplace_and_traceability_pages_render(self):
        recycler = make_user("+22997000020", "recycler")
        client = Client()
        client.force_login(recycler)
        self.assertEqual(client.get(reverse("marketplace:list")).status_code, 200)
        self.assertEqual(client.get(reverse("marketplace:mine")).status_code, 200)
        self.assertEqual(client.get(reverse("traceability:list")).status_code, 200)
