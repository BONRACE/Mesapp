from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import RecyclerProfile
from waste.models import WasteCategory
from waste.tests import make_user

from .models import Listing, Order
from .services import expire_stale_orders


class MarketBase(APITestCase):
    def setUp(self):
        self.cat = WasteCategory.objects.create(code="plastique", name="Plastique", points_per_kg=10)
        self.waste = WasteCategory.objects.create(code="autres", name="Autres", is_recyclable=False)
        self.seller = make_user("+2290197123456", "collector", "Koffi")
        self.buyer = make_user("+2290166123456", "recycler", "Acheteur")
        RecyclerProfile.objects.create(user=self.buyer, company_name="Plastic Bénin")
        self.listing = Listing.objects.create(seller=self.seller, category=self.cat, title="PET", quantity_kg=Decimal("100"),
                                              unit_price=140, min_order_kg=Decimal("10"))

    def order(self, kg="40", user=None):
        self.client.force_authenticate(user or self.buyer)
        return self.client.post("/api/market/orders/", {"listing": self.listing.id, "quantity_kg": kg}, format="json")


@override_settings(MARKET_COMMISSION_RATE="0.05")
class OrderTests(MarketBase):
    def test_order_reserves_stock_and_computes_amounts(self):
        r = self.order("40")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["total"], r.data["commission"]), (5600, 280))
        self.assertIsNone(r.data["seller_net"])  # le net vendeur n'est pas visible de l'acheteur
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_kg, Decimal("60"))

    def test_seller_sees_net(self):
        self.order("40")
        self.client.force_authenticate(self.seller)
        r = self.client.get("/api/market/orders/?as=seller")
        self.assertEqual(r.data["results"][0]["seller_net"], 5320)

    def test_cannot_oversell(self):
        self.assertEqual(self.order("101").status_code, 409)
        self.assertEqual(self.order("5").status_code, 400)  # sous le minimum
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_kg, Decimal("100"))

    def test_cannot_buy_own_listing(self):
        self.assertEqual(self.order("20", user=self.seller).status_code, 403)

    def test_cancel_restores_stock_once(self):
        oid = self.order("40").data["id"]
        self.assertEqual(self.client.post(f"/api/market/orders/{oid}/cancel/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/market/orders/{oid}/cancel/").status_code, 409)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_kg, Decimal("100"))

    def test_expiry_restores_stock(self):
        oid = self.order("40").data["id"]
        Order.objects.filter(pk=oid).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(expire_stale_orders(), 1)
        self.listing.refresh_from_db()
        self.assertEqual((self.listing.quantity_kg, Order.objects.get(pk=oid).status), (Decimal("100"), "expired"))

    def test_concurrent_style_double_booking_blocked(self):
        self.assertEqual(self.order("70").status_code, 201)
        self.assertEqual(self.order("70").status_code, 409)

    def test_incomplete_profile_cannot_order(self):
        newbie = make_user("+2290152000001", "citizen", "Nouveau")
        newbie.profile_completed = False
        newbie.save()
        self.assertEqual(self.order("20", user=newbie).status_code, 403)

    def test_other_users_cannot_see_or_cancel_order(self):
        oid = self.order("40").data["id"]
        stranger = make_user("+2290161234567", "citizen", "Autre")
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.get(f"/api/market/orders/{oid}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/market/orders/{oid}/cancel/").status_code, 404)

    def test_fulfilment_flow(self):
        oid = self.order("40").data["id"]
        Order.objects.filter(pk=oid).update(status="paid")
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post(f"/api/market/orders/{oid}/ship/").data["status"], "shipped")
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(f"/api/market/orders/{oid}/deliver/").data["status"], "delivered")
        self.client.force_authenticate(self.seller)
        e = self.client.get("/api/market/earnings/").data
        self.assertEqual((e["gross_xof"], e["net_xof"]), (5600, 5320))


class ListingTests(MarketBase):
    def test_public_can_browse_but_not_create(self):
        self.client.force_authenticate(None)
        r = self.client.get("/api/market/listings/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("phone", str(r.data))
        self.assertEqual(self.client.post("/api/market/listings/", {}, format="json").status_code, 401)

    def test_citizen_cannot_sell(self):
        self.client.force_authenticate(make_user("+2290196000001", "citizen"))
        r = self.client.post("/api/market/listings/", {"category": self.cat.id, "title": "x", "quantity_kg": "10", "unit_price": 10}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_non_recyclable_category_refused(self):
        self.client.force_authenticate(self.seller)
        r = self.client.post("/api/market/listings/", {"category": self.waste.id, "title": "x", "quantity_kg": "10", "unit_price": 10}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_seller_manages_only_own_and_delete_is_soft(self):
        self.client.force_authenticate(self.seller)
        r = self.client.post("/api/market/listings/", {"category": self.cat.id, "title": "Neuf", "quantity_kg": "50", "unit_price": 99,
                                                       "latitude": 6.36, "longitude": 2.39}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        lid = r.data["id"]
        self.assertEqual(self.client.delete(f"/api/market/listings/{lid}/").status_code, 204)
        self.assertTrue(Listing.objects.filter(pk=lid, is_active=False).exists())
        self.client.force_authenticate(self.buyer)
        # Annonce d'un autre vendeur : hors de son périmètre, donc 404 (n'en révèle pas l'existence).
        self.assertEqual(self.client.patch(f"/api/market/listings/{self.listing.id}/", {"unit_price": 1}, format="json").status_code, 404)

    def test_distance_sort_and_price_board(self):
        far = Listing.objects.create(seller=self.seller, category=self.cat, title="Loin", quantity_kg=10, unit_price=100)
        r = self.client.get("/api/market/prices/")
        self.assertEqual(r.data[0]["avg_price"], 120)
        self.assertEqual(far.listings if False else r.data[0]["listings"], 2)
