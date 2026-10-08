import io
import shutil
import tempfile
from datetime import time, timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from events.models import Event, TicketType
from orders.models import Order, Ticket, Withdrawal
from orders.services import PurchaseError, create_order, organizer_balance, pay_order, request_withdrawal, ticket_pdf

TMP_MEDIA = tempfile.mkdtemp()


def png(name="x.png"):
    buf = io.BytesIO()
    Image.new("RGB", (60, 60), (22, 163, 74)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP_MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NovaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        mk = lambda email, role, country, phone, **kw: User.objects.create_user(  # noqa: E731
            username=email, email=email, password="pw-test-1234", role=role, country=country, phone=phone,
            first_name="Test", last_name="User", sexe="M", **kw)
        self.orga = mk("o@t.test", "organisateur", "BJ", "+2290197000001", org_name="Orga Test")
        self.orga2 = mk("o2@t.test", "organisateur", "CI", "+2250707000002", org_name="Orga 2")
        self.fan = mk("f@t.test", "spectateur", "BJ", "+2290197000003")
        today = timezone.localdate()
        self.event = Event.objects.create(
            organizer=self.orga, name="Soirée Test", location="Cotonou", visual=png("v.png"),
            start_date=today + timedelta(days=10), end_date=today + timedelta(days=10), start_time=time(20, 0),
            purchase_deadline=today + timedelta(days=9), is_published=True)
        self.tt = TicketType.objects.create(event=self.event, name="Standard", price=10000, stock=5)

    # --- règles métier
    def test_commission_and_net(self):
        order = create_order(self.fan, self.tt, 2)
        self.assertEqual(order.total, 20000)
        self.assertEqual(order.commission, 1000)          # 5 %
        self.assertEqual(order.organizer_amount, 19000)

    def test_organizer_cannot_buy_own_event(self):
        with self.assertRaises(PurchaseError):
            create_order(self.orga, self.tt, 1)

    def test_organizer_can_buy_other_event(self):
        order = create_order(self.orga2, self.tt, 1)
        _, ok, _ = pay_order(order, "orange_ci", "+2250707000002", send_email=False)
        self.assertTrue(ok)

    def test_stock_limit(self):
        with self.assertRaises(PurchaseError):
            create_order(self.fan, self.tt, 6)

    def test_payment_methods_depend_on_country(self):
        order = create_order(self.fan, self.tt, 1)           # acheteur du Bénin
        with self.assertRaises(PurchaseError):
            pay_order(order, "wave_ci", "+2250707000009", send_email=False)   # Wave CI indisponible au Bénin
        _, ok, _ = pay_order(order, "mtn_bj", "+2290197000003", send_email=False)
        self.assertTrue(ok)

    def test_failed_payment_creates_no_tickets(self):
        order = create_order(self.fan, self.tt, 1)
        _, ok, msg = pay_order(order, "mtn_bj", "22901970000000000", send_email=False)
        self.assertFalse(ok)
        self.assertEqual(Ticket.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_paid_order_creates_tickets_email_and_pdf(self):
        order = create_order(self.fan, self.tt, 2)
        pay_order(order, "mtn_bj", "+2290197000003")
        self.assertEqual(Ticket.objects.filter(order=order).count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["f@t.test"])
        self.assertEqual(len([a for a in msg.attachments if a[2] == "application/pdf"]), 2)
        html = msg.alternatives[0][0]
        self.assertIn("Merci pour votre achat", html)
        self.assertIn("Soirée Test", html)
        pdf = ticket_pdf(Ticket.objects.first())
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_withdrawals(self):
        order = create_order(self.fan, self.tt, 3)           # net 28 500
        pay_order(order, "mtn_bj", "+2290197000003", send_email=False)
        self.assertEqual(organizer_balance(self.orga), 28500)
        with self.assertRaises(PurchaseError):
            request_withdrawal(self.orga, 30000, "mtn_bj", "+2290197000001")   # > solde
        with self.assertRaises(PurchaseError):
            request_withdrawal(self.orga, 500, "mtn_bj", "+2290197000001")     # < minimum
        with self.assertRaises(PurchaseError):
            request_withdrawal(self.orga, 5000, "card", "+2290197000001")      # pas de retrait par carte
        request_withdrawal(self.orga, 10000, "mtn_bj", "+2290197000001")
        self.assertEqual(organizer_balance(self.orga), 18500)
        self.assertEqual(Withdrawal.objects.count(), 1)

    # --- vues
    def test_registration_requires_valid_phone_for_country(self):
        data = {"last_name": "Dossou", "first_name": "Marc", "sexe": "M", "profession": "Dev", "email": "new@t.test",
                "country": "BJ", "phone": "12", "password1": "Sup3r-Secret-99", "password2": "Sup3r-Secret-99", "photo": png("p.png")}
        r = self.client.post(reverse("accounts:register_spectateur"), data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="new@t.test").exists())
        data.update(phone="97 00 00 99", photo=png("p2.png"))
        r = self.client.post(reverse("accounts:register_spectateur"), data)
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(email="new@t.test")
        self.assertEqual(u.phone, "+22997000099")
        self.assertEqual(u.role, "spectateur")

    def test_full_purchase_flow_over_http(self):
        self.client.login(username="f@t.test", password="pw-test-1234")
        r = self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": 2})
        order = Order.objects.get()
        self.assertRedirects(r, reverse("orders:pay", args=[order.reference]))
        self.assertEqual(self.client.get(reverse("orders:pay", args=[order.reference])).status_code, 200)
        r = self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "mtn_bj", "phone": "+2290197000003"})
        self.assertRedirects(r, reverse("orders:confirmation", args=[order.reference]))
        t = Ticket.objects.first()
        for name in ("orders:my_space", "orders:ticket"):
            args = [t.reference] if name == "orders:ticket" else []
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)
        pdf = self.client.get(reverse("orders:ticket_pdf", args=[t.reference]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertEqual(self.client.get(reverse("orders:ticket_qr", args=[t.reference]))["Content-Type"], "image/png")
        self.assertEqual(self.client.get(reverse("core:verify", args=[t.reference])).status_code, 200)

    def test_http_organizer_blocked_on_own_event(self):
        self.client.login(username="o@t.test", password="pw-test-1234")
        r = self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": 1}, follow=True)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(r, "propre événement")

    def test_spectator_cannot_access_organizer_dashboard(self):
        self.client.login(username="f@t.test", password="pw-test-1234")
        r = self.client.get(reverse("events:orga_dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_ticket_belongs_to_buyer(self):
        order = create_order(self.fan, self.tt, 1)
        pay_order(order, "mtn_bj", "+2290197000003", send_email=False)
        t = Ticket.objects.get()
        self.client.login(username="o2@t.test", password="pw-test-1234")
        self.assertEqual(self.client.get(reverse("orders:ticket", args=[t.reference])).status_code, 404)

    def test_organizer_pages_and_event_creation(self):
        self.client.login(username="o@t.test", password="pw-test-1234")
        for name in ("events:orga_dashboard", "events:create", "events:withdraw"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        today = timezone.localdate()
        data = {
            "name": "Nouvel événement", "location": "Porto-Novo", "description": "x", "visual": png("n.png"),
            "start_date": today + timedelta(days=30), "end_date": today + timedelta(days=30), "start_time": "18:00",
            "purchase_deadline": today + timedelta(days=29),
            "tt-TOTAL_FORMS": "2", "tt-INITIAL_FORMS": "0", "tt-MIN_NUM_FORMS": "0", "tt-MAX_NUM_FORMS": "1000",
            "tt-0-name": "Standard", "tt-0-price": "5000", "tt-0-stock": "100",
            "tt-1-name": "VIP", "tt-1-price": "15000", "tt-1-stock": "20",
        }
        r = self.client.post(reverse("events:create"), data)
        self.assertEqual(r.status_code, 302)
        ev = Event.objects.get(name="Nouvel événement")
        self.assertFalse(ev.is_published)
        self.assertEqual(ev.ticket_types.count(), 2)
        self.client.post(reverse("events:toggle", args=[ev.pk]))
        ev.refresh_from_db()
        self.assertTrue(ev.is_published)

    def test_event_requires_ticket_type(self):
        self.client.login(username="o@t.test", password="pw-test-1234")
        today = timezone.localdate()
        data = {
            "name": "Sans ticket", "location": "X", "visual": png("n.png"),
            "start_date": today, "end_date": today, "start_time": "18:00", "purchase_deadline": today,
            "tt-TOTAL_FORMS": "1", "tt-INITIAL_FORMS": "0", "tt-MIN_NUM_FORMS": "0", "tt-MAX_NUM_FORMS": "1000",
            "tt-0-name": "", "tt-0-price": "", "tt-0-stock": "",
        }
        r = self.client.post(reverse("events:create"), data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Event.objects.filter(name="Sans ticket").exists())

    def test_home_and_detail_pages(self):
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)
        self.assertContains(self.client.get(reverse("events:detail", args=[self.event.pk])), "Soirée Test")
