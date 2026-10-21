"""Parcours principal : achat → paiement → tickets → reçu e-mail ; règles métier."""
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.templatetags.nt import fcfa
from core.testutils import cleanup_media, image_file, make_event, make_user, media_override
from payments.models import Payment
from payments.services import organizer_balance
from tickets.models import Order, Ticket


@media_override
class PurchaseFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cleanup_media()

    def setUp(self):
        self.orga = make_user("orga@t.nt", "organisateur")
        self.other = make_user("orga2@t.nt", "organisateur", phone="+2290196123456")
        self.buyer = make_user("buyer@t.nt", phone="+2290195234567", first_name="Eric", last_name="HOUN")
        self.event = make_event(self.orga)

    def buy(self, user, qty=2, **extra):
        self.client.force_login(user)
        ttype = self.event.ticket_types.get()
        r = self.client.post(reverse("tickets:buy", args=[self.event.slug]), dict(ticket_type=ttype.pk, quantity=qty, **extra))
        return r

    def pay(self, payment, phone="+2290195234567", method="mtn_momo"):
        # on_commit : en test (transaction englobante) on exécute explicitement les rappels
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(payment.get_checkout_url(), dict(method=method, phone=phone))

    def test_full_flow_issues_tickets_and_sends_receipt(self):
        r = self.buy(self.buyer)
        payment = Payment.objects.get()
        self.assertRedirects(r, payment.get_checkout_url(), fetch_redirect_response=False)
        self.assertEqual((payment.amount, payment.status), (10000, "pending"))
        self.assertEqual(Ticket.objects.count(), 0)  # pas de ticket avant paiement
        r = self.pay(payment)
        order = Order.objects.get()
        self.assertRedirects(r, reverse("tickets:order_detail", args=[order.reference]), fetch_redirect_response=False)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "succeeded")
        self.assertEqual(order.status, "paid")
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(self.event.ticket_types.get().sold, 2)
        # reçu automatique
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["buyer@t.nt"])
        html = msg.alternatives[0][0]
        for needle in ["Merci pour votre achat", "Concert Test", "Standard", order.reference, fcfa(10000), "Powered by", "cid:qr@novatickets", "Validé"]:
            self.assertIn(needle, html)
        self.assertTrue(any(a[0].endswith(".pdf") for a in msg.attachments if isinstance(a, tuple)))

    def test_commission_and_balance(self):
        self.buy(self.buyer)
        self.pay(Payment.objects.get())
        order = Order.objects.get()
        self.assertEqual(order.commission, 500)  # 5 % de 10 000
        self.assertEqual(organizer_balance(self.orga), 9500)

    def test_organizer_cannot_buy_own_event_but_can_buy_others(self):
        r = self.buy(self.orga)
        self.assertRedirects(r, self.event.get_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())
        self.buy(self.other, qty=1)
        self.assertEqual(Order.objects.count(), 1)  # un autre organisateur peut acheter

    def test_gift_ticket_issued_to_friend(self):
        self.buy(self.buyer, qty=1, for_friend="on", friend_last_name="AMOUSSOU", friend_first_name="Koffi",
                 friend_email="koffi@t.nt", friend_phone="+2290197555123", friend_sexe="M")
        self.pay(Payment.objects.get())
        t = Ticket.objects.get()
        self.assertEqual((t.holder_last_name, t.holder_first_name, t.holder_email), ("AMOUSSOU", "Koffi", "koffi@t.nt"))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["buyer@t.nt", "koffi@t.nt"])

    def test_gift_requires_contact(self):
        self.buy(self.buyer, qty=1, for_friend="on", friend_last_name="A", friend_first_name="B")
        self.assertFalse(Order.objects.exists())

    def test_declined_payment_issues_nothing(self):
        self.buy(self.buyer)
        r = self.pay(Payment.objects.get(), phone="+2290195234500")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Payment.objects.get().status, "failed")
        # nouvelle tentative réussie
        self.pay(Payment.objects.get())
        self.assertEqual(Ticket.objects.count(), 2)

    def test_cannot_oversell(self):
        r = self.buy(self.buyer, qty=11)  # stock 10 / max 10 par commande
        self.assertFalse(Order.objects.exists())
        self.event.ticket_types.update(stock=1)
        self.buy(self.buyer, qty=2)
        self.assertFalse(Order.objects.exists())

    def test_payment_idempotent_no_double_tickets(self):
        self.buy(self.buyer)
        payment = Payment.objects.get()
        self.pay(payment); self.pay(payment)
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_free_ticket_confirmed_without_payment_step(self):
        self.event.ticket_types.update(price=0)
        with self.captureOnCommitCallbacks(execute=True):
            self.buy(self.buyer, qty=1)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_unpublished_event_not_buyable(self):
        self.event.is_published = False
        self.event.save()
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse("tickets:buy", args=[self.event.slug])).status_code, 404)

    def test_ticket_pages_and_pdf_access_control(self):
        self.buy(self.buyer)
        self.pay(Payment.objects.get())
        t = Ticket.objects.first()
        self.assertContains(self.client.get(t.get_absolute_url()), t.reference)
        pdf = self.client.get(reverse("tickets:pdf", args=[t.reference]))
        self.assertEqual((pdf.status_code, pdf["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(self.client.get(reverse("tickets:qr", args=[t.reference]))["Content-Type"], "image/png")
        # un autre utilisateur ne voit pas ce ticket
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(t.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("tickets:pdf", args=[t.reference])).status_code, 404)

    def test_only_event_organizer_can_validate_entry(self):
        self.buy(self.buyer, qty=1)
        self.pay(Payment.objects.get())
        t = Ticket.objects.get()
        url = reverse("tickets:mark_used", args=[t.token])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.orga)
        self.client.post(url)
        t.refresh_from_db()
        self.assertIsNotNone(t.used_at)

    def test_login_required_everywhere(self):
        self.client.logout()
        for url in [reverse("tickets:dashboard"), reverse("tickets:buy", args=[self.event.slug]), reverse("cards:create"),
                    reverse("payments:history")]:
            self.assertEqual(self.client.get(url).status_code, 302, url)
