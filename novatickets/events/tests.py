from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.testutils import cleanup_media, image_file, make_event, make_user, media_override
from events.models import Event
from payments.models import Withdrawal
from payments.services import organizer_balance


@media_override
class EventTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cleanup_media()

    def setUp(self):
        self.orga = make_user("o@t.nt", "organisateur")
        self.spec = make_user("s@t.nt", phone="+2290196123456")

    def form_data(self, **over):
        d = dict(name="Mon Festival", description="Super", venue="Stade", city="Cotonou",
                 start_date=(timezone.localdate() + timedelta(days=20)).isoformat(),
                 end_date=(timezone.localdate() + timedelta(days=21)).isoformat(), start_time="18:00",
                 sales_deadline=(timezone.now() + timedelta(days=19)).strftime("%Y-%m-%dT%H:%M"),
                 visual=image_file("v.png"), logo=image_file("l.png"),
                 **{"types-TOTAL_FORMS": "2", "types-INITIAL_FORMS": "0", "types-MIN_NUM_FORMS": "0", "types-MAX_NUM_FORMS": "1000",
                    "types-0-name": "Standard", "types-0-price": "5000", "types-0-stock": "100",
                    "types-1-name": "VIP", "types-1-price": "15000", "types-1-stock": "20"})
        d.update(over)
        return d

    def test_create_event_with_dynamic_ticket_types(self):
        self.client.force_login(self.orga)
        r = self.client.post(reverse("events:create"), self.form_data())
        ev = Event.objects.get()
        self.assertRedirects(r, reverse("events:manage", args=[ev.slug]), fetch_redirect_response=False)
        self.assertFalse(ev.is_published)  # brouillon tant qu'on ne publie pas
        self.assertEqual(sorted(ev.ticket_types.values_list("name", "price", "stock")), [("Standard", 5000, 100), ("VIP", 15000, 20)])

    def test_requires_at_least_one_ticket_type_and_valid_dates(self):
        self.client.force_login(self.orga)
        bad = self.form_data(**{"types-0-DELETE": "on", "types-1-DELETE": "on"})
        self.assertEqual(self.client.post(reverse("events:create"), bad).status_code, 200)
        bad = self.form_data(end_date=(timezone.localdate() + timedelta(days=1)).isoformat())
        self.assertEqual(self.client.post(reverse("events:create"), bad).status_code, 200)
        self.assertFalse(Event.objects.exists())

    def test_publish_makes_event_public(self):
        ev = make_event(self.orga, published=False)
        self.assertEqual(self.client.get(ev.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("events:list")), ev.name)
        self.client.force_login(self.orga)
        self.client.post(reverse("events:toggle_publish", args=[ev.slug]))
        self.client.logout()
        self.assertEqual(self.client.get(ev.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get(reverse("events:list")), ev.name)

    def test_spectator_cannot_access_organizer_space(self):
        self.client.force_login(self.spec)
        for name in ("events:dashboard", "events:create", "payments:withdrawals"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_organizer_cannot_touch_others_events(self):
        ev = make_event(self.orga)
        other = make_user("o2@t.nt", "organisateur", phone="+2290195234567")
        self.client.force_login(other)
        for name in ("events:manage", "events:edit"):
            self.assertEqual(self.client.get(reverse(name, args=[ev.slug])).status_code, 404, name)
        self.assertEqual(self.client.post(reverse("events:toggle_publish", args=[ev.slug])).status_code, 404)
        self.assertEqual(self.client.post(reverse("events:delete", args=[ev.slug])).status_code, 404)

    def test_withdrawal_flow_and_balance_guard(self):
        from tickets.services import create_order
        from payments.services import process_payment
        ev = make_event(self.orga, price=10000)
        order, payment = create_order(self.spec, ev.ticket_types.get(), 3)
        process_payment(payment, "mtn_momo", self.spec.phone)
        self.assertEqual(organizer_balance(self.orga), 28500)  # 30 000 − 5 %
        self.client.force_login(self.orga)
        r = self.client.post(reverse("payments:withdrawals"), dict(amount=20000, method="mtn_momo", phone="01 97 12 34 56"))
        self.assertRedirects(r, reverse("payments:withdrawals"), fetch_redirect_response=False)
        w = Withdrawal.objects.get()
        self.assertEqual((w.amount, w.status), (20000, "completed"))
        self.assertEqual(organizer_balance(self.orga), 8500)
        # montant supérieur au solde refusé
        r = self.client.post(reverse("payments:withdrawals"), dict(amount=9000, method="mtn_momo", phone="01 97 12 34 56"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Withdrawal.objects.count(), 1)
        self.assertContains(self.client.get(reverse("payments:withdrawals")), "Historique des retraits")

    def test_payment_methods_depend_on_country(self):
        from payments.methods import payment_methods
        self.assertEqual([c for c, _ in payment_methods("BJ")], ["mtn_momo", "moov_money", "celtiis_cash", "card"])
        self.assertIn("wave", [c for c, _ in payment_methods("SN")])
        self.assertEqual([c for c, _ in payment_methods("FR")], ["card"])
