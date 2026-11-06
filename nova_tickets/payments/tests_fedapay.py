import hashlib
import hmac
import json
import time
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests_security import event, user
from orders.models import Order
from orders.services import create_order
from payments import fedapay
from payments.models import Transaction

SETTINGS = dict(PAYMENT_GATEWAY="fedapay", FEDAPAY_ENV="sandbox", FEDAPAY_SECRET_KEY="sk_sandbox_test",
                FEDAPAY_WEBHOOK_SECRET="wh_sandbox_secret_value")


class FakeFeda:
    """Simule l'API FedaPay : enregistre les appels et renvoie un statut configurable."""
    def __init__(self, status="pending", amount=None):
        self.status, self.amount, self.calls = status, amount, []

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "POST" and path == "/transactions":
            self.amount = payload["amount"] if self.amount is None else self.amount
            return {"v1/transaction": {"id": 777, "status": "pending", "amount": payload["amount"]}}
        if path.endswith("/token"):
            return {"token": "tok", "url": "https://sandbox-process.fedapay.com/tok"}
        return {"v1/transaction": {"id": 777, "status": self.status, "amount": self.amount}}


@override_settings(**SETTINGS)
class FedaPayTests(TestCase):
    def setUp(self):
        self.orga, self.fan = user("organisateur", 21), user("spectateur", 22)
        self.ev, self.tt = event(self.orga)
        self.client.force_login(self.fan)

    def start(self, fake):
        order = create_order(self.fan, self.tt, 2)
        with mock.patch.object(fedapay, "_request", fake):
            r = self.client.post(reverse("orders:pay", args=[order.reference]), {})
        return order, r

    def test_checkout_redirects_to_fedapay_with_server_side_amount(self):
        fake = FakeFeda()
        order, r = self.start(fake)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("https://sandbox-process.fedapay.com/"))
        tx = Transaction.objects.get()
        self.assertEqual((tx.provider, tx.gateway_reference, tx.amount), ("FEDA", "777", order.total))
        self.assertEqual(fake.calls[0][2]["amount"], int(order.total))
        self.assertEqual(fake.calls[0][2]["currency"], {"iso": "XOF"})

    def test_return_page_validates_after_api_says_approved(self):
        order, _ = self.start(FakeFeda())
        tx = Transaction.objects.get()
        with mock.patch.object(fedapay, "_request", FakeFeda("approved", amount=int(tx.amount))):
            self.client.get(reverse("payments:status", args=[tx.pk]))
        tx.refresh_from_db(); order.refresh_from_db()
        self.assertEqual(tx.status, "SUCCESS")
        self.assertEqual(order.status, Order.Status.PAID)

    def test_wrong_amount_from_api_is_never_validated(self):
        order, _ = self.start(FakeFeda())
        tx = Transaction.objects.get()
        with mock.patch.object(fedapay, "_request", FakeFeda("approved", amount=1)):
            self.client.get(reverse("payments:status", args=[tx.pk]))
        tx.refresh_from_db(); order.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_declined_marks_failed(self):
        self.start(FakeFeda())
        tx = Transaction.objects.get()
        with mock.patch.object(fedapay, "_request", FakeFeda("declined")):
            self.client.get(reverse("payments:status", args=[tx.pk]))
        tx.refresh_from_db()
        self.assertEqual(tx.status, "FAILED")

    def test_pending_page_reuses_checkout_link(self):
        order, _ = self.start(FakeFeda())
        with mock.patch.object(fedapay, "_request", FakeFeda()) as m:
            r = self.client.post(reverse("orders:pay", args=[order.reference]), {})
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertTrue(r["Location"].startswith("https://sandbox-process.fedapay.com/"))

    def test_api_error_marks_failed_without_leaking_key(self):
        from payments.services import PaymentError
        order = create_order(self.fan, self.tt, 1)
        with mock.patch.object(fedapay, "_request", side_effect=PaymentError("indisponible")):
            r = self.client.post(reverse("orders:pay", args=[order.reference]), {}, follow=True)
        self.assertNotContains(r, "sk_sandbox_test")
        self.assertEqual(Transaction.objects.get().status, "FAILED")

    # --- webhook
    def sign(self, body, ts=None):
        ts = str(int(ts or time.time()))
        return f"t={ts},s=" + hmac.new(b"wh_sandbox_secret_value", ts.encode() + b"." + body, hashlib.sha256).hexdigest()

    def post_hook(self, body, header):
        return self.client.post(reverse("payments:webhook"), data=body, content_type="application/json",
                                headers={"X-FEDAPAY-SIGNATURE": header})

    def test_webhook_rejects_bad_or_missing_signature(self):
        body = json.dumps({"name": "transaction.approved", "entity": {"id": 777}}).encode()
        self.assertEqual(self.post_hook(body, "t=1,s=deadbeef").status_code, 403)
        self.assertEqual(self.post_hook(body, "").status_code, 403)

    def test_webhook_rejects_old_timestamp(self):
        body = b'{"entity":{"id":777}}'
        self.assertEqual(self.post_hook(body, self.sign(body, time.time() - 99999)).status_code, 403)

    def test_webhook_valid_signature_triggers_api_check_not_trust(self):
        self.start(FakeFeda())
        tx = Transaction.objects.get()
        body = json.dumps({"name": "transaction.approved", "entity": {"id": 777, "status": "approved"}}).encode()
        with mock.patch.object(fedapay, "_request", FakeFeda("pending")):        # le webhook dit approved, l'API dit pending
            r = self.post_hook(body, self.sign(body))
        self.assertEqual(r.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")
        with mock.patch.object(fedapay, "_request", FakeFeda("approved", amount=int(tx.amount))):
            self.assertEqual(self.post_hook(body, self.sign(body)).status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "SUCCESS")

    def test_generic_signature_webhook_disabled_when_fedapay_in_production(self):
        with override_settings(DEBUG=False):
            r = self.client.post(reverse("payments:webhook"), data=b"{}", content_type="application/json", headers={"X-Signature": "x"})
        self.assertEqual(r.status_code, 403)

    def test_subscription_and_card_use_fedapay(self):
        self.client.force_login(self.orga)
        with mock.patch.object(fedapay, "_request", FakeFeda()):
            r = self.client.post(reverse("subscriptions:pay"), {})
        self.assertTrue(r["Location"].startswith("https://sandbox-process.fedapay.com/"))
        tx = Transaction.objects.get()
        self.assertEqual((tx.provider, tx.purpose, int(tx.amount)), ("FEDA", "subscription", 5000))
        with mock.patch.object(fedapay, "_request", FakeFeda("approved", amount=5000)):
            self.client.get(reverse("payments:status", args=[tx.pk]))
        from subscriptions.services import is_active
        self.assertTrue(is_active(self.orga))

    def test_pages_show_fedapay_button(self):
        order = create_order(self.fan, self.tt, 1)
        self.assertContains(self.client.get(reverse("orders:pay", args=[order.reference])), "avec FedaPay")
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("subscriptions:index")), "avec FedaPay")

    @override_settings(FEDAPAY_SECRET_KEY="")
    def test_disabled_without_key(self):
        self.assertFalse(fedapay.enabled())
