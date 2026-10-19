"""Envoi du reçu : échec visible, bouton « Renvoyer le reçu », mode console."""
from datetime import date, time, timedelta

from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.tests import make_user
from events.models import Event, TicketType
from orders.models import Order


class BrokenBackend(BaseEmailBackend):
    """Simule un serveur SMTP injoignable ou des identifiants refusés."""

    def send_messages(self, email_messages):
        raise ConnectionRefusedError("SMTP injoignable")


class ReceiptDeliveryTests(TestCase):
    def setUp(self):
        self.orga = make_user("orga", User.ORGANISATEUR, org_name="Orga Prod")
        self.spec = make_user("spec", User.SPECTATEUR)
        d = date.today() + timedelta(days=5)
        self.event = Event.objects.create(organizer=self.orga, name="Show", start_date=d, end_date=d,
                                          start_time=time(19, 0), sales_deadline=d, status=Event.PUBLISHED)
        self.tt = TicketType.objects.create(event=self.event, name="VIP", price=10000, stock=20)

    def _order_and_pay(self):
        self.client.force_login(self.spec)
        self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": 1})
        order = Order.objects.latest("id")
        r = self.client.post(reverse("orders:pay", args=[order.reference]),
                             {"payment_method": "MTN Mobile Money", "payment_phone": "97000001"}, follow=True)
        order.refresh_from_db()
        return order, [str(m) for m in r.context["messages"]]

    def test_payment_survives_a_broken_mail_server_and_tells_the_user(self):
        with override_settings(EMAIL_BACKEND="core.test_email.BrokenBackend"), self.assertLogs("orders.services", "ERROR"):
            order, msgs = self._order_and_pay()
        self.assertEqual(order.status, Order.PAID)           # le paiement et les billets ne dépendent pas de l'e-mail
        self.assertEqual(order.tickets.count(), 1)
        self.assertTrue(any("n'a pas pu être envoyé" in m for m in msgs), msgs)

    def test_console_mode_explains_that_nothing_is_really_sent(self):
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            _, msgs = self._order_and_pay()
        self.assertTrue(any("Mode développement" in m for m in msgs), msgs)

    def test_resend_receipt(self):
        order, _ = self._order_and_pay()
        self.assertEqual(len(mail.outbox), 1)
        r = self.client.post(reverse("orders:resend_receipt", args=[order.reference]), follow=True)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, ["spec@t.test"])
        self.assertTrue(any("Reçu renvoyé" in str(m) for m in r.context["messages"]))
        self.assertContains(r, "Renvoyer le reçu")             # le bouton est bien sur « Mes billets »

    def test_resend_is_private_and_only_for_paid_orders(self):
        order, _ = self._order_and_pay()
        other = make_user("other", User.SPECTATEUR)
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("orders:resend_receipt", args=[order.reference])).status_code, 404)
        self.client.force_login(self.spec)
        self.client.post(reverse("orders:buy", args=[self.event.slug]), {"ticket_type": self.tt.pk, "quantity": 1})
        pending = Order.objects.filter(status=Order.PENDING).latest("id")
        self.assertEqual(self.client.post(reverse("orders:resend_receipt", args=[pending.reference])).status_code, 404)
        self.assertEqual(self.client.get(reverse("orders:resend_receipt", args=[order.reference])).status_code, 405)
