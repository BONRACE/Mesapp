from datetime import date, time, timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from events.models import Event, TicketType
from orders.models import Order, Ticket


def make_user(username, role, country="BJ", **kw):
    u = User(username=username, role=role, country=country, phone="+229 97000001",
             first_name="Test", last_name=username.upper(), email=f"{username}@t.test", sexe="F", **kw)
    u.set_password("pass1234")
    u.save()
    return u


class FlowTests(TestCase):
    def setUp(self):
        self.orga = make_user("orga", User.ORGANISATEUR, org_name="Orga Prod")
        self.orga2 = make_user("orga2", User.ORGANISATEUR, org_name="Other")
        self.spec = make_user("spec", User.SPECTATEUR)
        today = date.today()
        self.event = Event.objects.create(
            organizer=self.orga, name="Show", start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=5), start_time=time(19, 0),
            sales_deadline=today + timedelta(days=5), status=Event.PUBLISHED)
        self.tt = TicketType.objects.create(event=self.event, name="VIP", price=10000, stock=5)

    def _buy_and_pay(self, user, qty=2, phone="97000001", method="MTN Mobile Money"):
        self.client.force_login(user)
        r = self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": qty})
        order = Order.objects.latest("id")
        self.assertRedirects(r, reverse("orders:pay", args=[order.reference]))
        return order, self.client.post(reverse("orders:pay", args=[order.reference]),
                                       {"payment_method": method, "payment_phone": phone})

    def test_pages_render_with_mobile_and_desktop_layout(self):
        r = self.client.get("/")
        self.assertContains(r, 'name="viewport"')
        self.assertContains(r, "md:hidden")       # barre du bas smartphone
        self.assertContains(r, "hidden md:flex")  # navigation ordinateur
        self.assertEqual(self.client.get(self.event.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:register", args=["spectateur"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:register", args=["organisateur"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)

    def test_registration_adds_dial_code(self):
        r = self.client.post(reverse("accounts:register", args=["organisateur"]), {
            "last_name": "N", "first_name": "P", "username": "newo", "email": "n@t.test", "sexe": "M",
            "profession": "x", "country": "CI", "phone": "07 00 00 00 00", "org_name": "Org",
            "password1": "abcdef", "password2": "abcdef"})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="newo")
        self.assertEqual(u.role, "organisateur")
        self.assertTrue(u.phone.startswith("+225"))

    def test_phone_is_mandatory(self):
        r = self.client.post(reverse("accounts:register", args=["organisateur"]), {
            "last_name": "N", "first_name": "P", "username": "x2", "email": "n@t.test", "sexe": "M",
            "country": "BJ", "phone": "", "org_name": "Org", "password1": "abcdef", "password2": "abcdef"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="x2").exists())

    def test_purchase_commission_email_and_tickets(self):
        order, r = self._buy_and_pay(self.spec)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(order.total, 20000)
        self.assertEqual(order.commission, 1000)   # 5 %
        self.assertEqual(order.net_amount, 19000)
        self.assertEqual(order.tickets.count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Merci pour votre achat", mail.outbox[0].alternatives[0][0])
        self.assertEqual(self.orga.net_earnings, 19000)

    def test_organizer_cannot_buy_own_event_but_can_buy_other(self):
        self.client.force_login(self.orga)
        self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": 1})
        self.assertEqual(Order.objects.count(), 0)
        self.client.force_login(self.orga2)
        self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": 1})
        self.assertEqual(Order.objects.count(), 1)

    def test_payment_failure_and_stock(self):
        order, r = self._buy_and_pay(self.spec, phone="97000000")  # finit par 0000 => refus
        order.refresh_from_db()
        self.assertEqual(order.status, Order.FAILED)
        self.assertEqual(Ticket.objects.count(), 0)
        self.client.force_login(self.spec)
        self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": 6})
        self.assertEqual(Order.objects.filter(status=Order.PENDING).count(), 0)

    def test_ticket_pages_pdf_qr_and_ownership(self):
        order, _ = self._buy_and_pay(self.spec, qty=1)
        t = order.tickets.first()
        self.assertEqual(self.client.get(t.get_absolute_url()).status_code, 200)
        pdf = self.client.get(reverse("orders:ticket_pdf", args=[t.code]))
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))
        qr = self.client.get(reverse("orders:ticket_qr", args=[t.code]))
        self.assertEqual(qr["Content-Type"], "image/png")
        self.client.force_login(self.orga2)
        self.assertEqual(self.client.get(t.get_absolute_url()).status_code, 403)

    def test_verify_and_validate_by_organizer(self):
        order, _ = self._buy_and_pay(self.spec, qty=1)
        t = order.tickets.first()
        self.client.force_login(self.orga)
        self.client.post(reverse("orders:verify", args=[t.code]))
        t.refresh_from_db()
        self.assertTrue(t.used)

    def test_withdrawal(self):
        self._buy_and_pay(self.spec, qty=2)  # net 19000
        self.client.force_login(self.orga)
        self.client.post(reverse("core:withdraw"), {"amount": "50000", "method": "MTN Mobile Money", "phone": "97000001"})
        self.assertEqual(self.orga.withdrawals.count(), 0)  # supérieur au solde
        self.client.post(reverse("core:withdraw"), {"amount": "10000", "method": "MTN Mobile Money", "phone": "97000001"})
        self.assertEqual(self.orga.withdrawals.count(), 1)
        self.assertEqual(User.objects.get(pk=self.orga.pk).available_balance, 9000)
        self.client.post(reverse("core:withdraw"), {"amount": "1000", "method": "Carte bancaire", "phone": "97000001"})
        self.assertEqual(self.orga.withdrawals.count(), 1)  # carte non autorisée pour un retrait

    def test_dashboards_and_event_creation(self):
        self._buy_and_pay(self.spec)
        self.client.force_login(self.spec)
        self.assertContains(self.client.get(reverse("core:spectateur_dashboard")), "Show")
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("core:organizer_dashboard")), "Solde disponible")
        r = self.client.post(reverse("events:create"), {
            "name": "Nouveau", "start_date": "2027-01-10", "end_date": "2027-01-10", "start_time": "18:00",
            "sales_deadline": "2027-01-10",
            "ticket_types-TOTAL_FORMS": "1", "ticket_types-INITIAL_FORMS": "0",
            "ticket_types-MIN_NUM_FORMS": "0", "ticket_types-MAX_NUM_FORMS": "1000",
            "ticket_types-0-name": "Std", "ticket_types-0-price": "2000", "ticket_types-0-stock": "50"})
        self.assertEqual(r.status_code, 302)
        ev = Event.objects.get(name="Nouveau")
        self.assertEqual(ev.status, Event.DRAFT)
        self.client.post(reverse("events:toggle_publish", args=[ev.pk]))
        ev.refresh_from_db()
        self.assertTrue(ev.is_published)
        self.client.force_login(self.spec)
        self.assertEqual(self.client.get(reverse("events:create")).status_code, 403)
