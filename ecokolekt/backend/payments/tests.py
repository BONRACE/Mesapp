from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from marketplace.models import Listing, Order
from marketplace.tests import MarketBase

from .models import Payment
from .providers import CinetPayProvider, FedaPayProvider, ProviderError


@override_settings(PAYMENT_DEFAULT_PROVIDER="mock")
class PaymentFlowTests(MarketBase):
    def _pay(self, kg="40"):
        oid = self.order(kg).data["id"]
        r = self.client.post("/api/payments/initiate/", {"order": oid, "method": "mobile_money"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return oid, r.data["id"]

    def _confirm(self, pid, outcome="success"):
        return self.client.post(f"/api/payments/mock/{pid}/confirm/", {"outcome": outcome}, format="json")

    def test_success_marks_order_paid_and_is_idempotent(self):
        oid, pid = self._pay()
        self.assertEqual(self._confirm(pid).data["status"], "succeeded")
        self.assertEqual(self._confirm(pid, "failed").data["status"], "succeeded")  # un paiement réussi ne régresse jamais
        o = Order.objects.get(pk=oid)
        self.assertEqual((o.status, o.paid_at is not None), ("paid", True))

    def test_failure_keeps_order_payable_and_retry_works(self):
        oid, pid = self._pay()
        self.assertEqual(self._confirm(pid, "failed").data["status"], "failed")
        self.assertEqual(Order.objects.get(pk=oid).status, "pending_payment")
        r = self.client.post("/api/payments/initiate/", {"order": oid}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_cannot_pay_someone_elses_order_or_confirm_their_payment(self):
        oid, pid = self._pay()
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post("/api/payments/initiate/", {"order": oid}, format="json").status_code, 404)
        self.assertEqual(self._confirm(pid).status_code, 404)
        self.assertEqual(self.client.get(f"/api/payments/{pid}/").status_code, 404)

    def test_paid_order_cannot_be_paid_again(self):
        oid, pid = self._pay()
        self._confirm(pid)
        self.assertEqual(self.client.post("/api/payments/initiate/", {"order": oid}, format="json").status_code, 409)

    def test_double_payment_flagged_for_refund(self):
        oid, p1 = self._pay()
        p2 = self.client.post("/api/payments/initiate/", {"order": oid}, format="json").data["id"]
        self._confirm(p1)
        self._confirm(p2)
        self.assertEqual(list(Payment.objects.filter(order_id=oid).order_by("created_at").values_list("needs_refund", flat=True)), [False, True])

    def test_late_payment_after_expiry_revives_order_if_stock_remains(self):
        oid, pid = self._pay("40")
        Order.objects.filter(pk=oid).update(created_at=timezone.now() - timedelta(hours=1))
        self.client.get("/api/market/orders/")  # déclenche l'expiration
        self.assertEqual(Order.objects.get(pk=oid).status, "expired")
        self._confirm(pid)
        o = Order.objects.get(pk=oid)
        self.listing.refresh_from_db()
        self.assertEqual((o.status, self.listing.quantity_kg), ("paid", Decimal("60")))
        self.assertFalse(Payment.objects.get(pk=pid).needs_refund)

    def test_late_payment_without_stock_is_flagged_not_honoured(self):
        oid, pid = self._pay("40")
        Order.objects.filter(pk=oid).update(created_at=timezone.now() - timedelta(hours=1))
        self.client.get("/api/market/orders/")
        Listing.objects.filter(pk=self.listing.pk).update(quantity_kg=Decimal("5"))  # vendu entre-temps
        self._confirm(pid)
        self.assertEqual(Order.objects.get(pk=oid).status, "expired")
        self.assertTrue(Payment.objects.get(pk=pid).needs_refund)

    @override_settings(PAYMENT_DEFAULT_PROVIDER="fedapay")
    def test_mock_confirm_disabled_with_real_provider(self):
        oid, pid = self._pay_as_mock_payment()
        self.assertEqual(self._confirm(pid).status_code, 404)

    def _pay_as_mock_payment(self):
        oid = self.order("40").data["id"]
        p = Payment.objects.create(order_id=oid, payer=self.buyer, provider="mock", amount=5600)
        return oid, p.id


@override_settings(PAYMENT_DEFAULT_PROVIDER="fedapay", FEDAPAY_SECRET_KEY="sk_test")
class FedaPayWebhookTests(MarketBase):
    """Un webhook (même falsifié) ne valide jamais un paiement : le statut est relu chez FedaPay."""

    def setUp(self):
        super().setUp()
        oid = self.order("40").data["id"]
        self.payment = Payment.objects.create(order_id=oid, payer=self.buyer, provider="fedapay", provider_ref="777", amount=5600)
        self.client.force_authenticate(None)

    def _hook(self, remote_status):
        with mock.patch.object(FedaPayProvider, "_call", return_value={"v1/transaction": {"id": 777, "status": remote_status}}):
            return self.client.post("/api/payments/webhook/fedapay/", {"name": "transaction.approved", "entity": {"id": 777, "status": "approved"}}, format="json")

    def test_forged_approved_webhook_ignored_when_remote_says_pending(self):
        self.assertEqual(self._hook("pending").status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_genuine_webhook_confirms_via_remote_status(self):
        self._hook("approved")
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.order.status), ("succeeded", "paid"))

    def test_declined_marks_failed_and_unknown_ref_is_harmless(self):
        self._hook("declined")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        r = self.client.post("/api/payments/webhook/fedapay/", {"entity": {"id": 999}}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/api/payments/webhook/fedapay/", {"hello": 1}, format="json").status_code, 400)

    def test_unwrap_tolerates_envelope_shapes(self):
        u = FedaPayProvider._unwrap
        self.assertEqual(u({"id": 1})["id"], 1)
        self.assertEqual(u({"v1/transaction": {"id": 2}})["id"], 2)
        self.assertEqual(u({"v1/transactions": [{"id": 3}]})["id"], 3)


@override_settings(PAYMENT_DEFAULT_PROVIDER="cinetpay", CINETPAY_API_KEY="k", CINETPAY_SITE_ID="1")
class CinetPayTests(MarketBase):
    """CinetPay : création du lien, relecture du statut côté serveur, webhook formulaire non cru."""

    def setUp(self):
        super().setUp()
        oid = self.order("40").data["id"]
        self.payment = Payment.objects.create(order_id=oid, payer=self.buyer, provider="cinetpay",
                                              provider_ref="EKabc", amount=5602)

    def _check(self, code="00", status="ACCEPTED", amount="5605"):
        return {"code": code, "message": "x", "data": {"status": status, "amount": amount}}

    def test_amount_rounded_up_to_multiple_of_five(self):
        self.assertEqual(CinetPayProvider.amount_for(self.payment), 5605)

    def test_create_returns_payment_url(self):
        reply = {"code": "201", "data": {"payment_url": "https://checkout.cinetpay.com/payment/tok"}}
        with mock.patch.object(CinetPayProvider, "_post", return_value=reply) as post:
            info = CinetPayProvider().create(self.payment, self.payment.order, self.buyer)
        self.assertTrue(info["checkout_url"].startswith("https://checkout.cinetpay.com/"))
        self.assertEqual(post.call_args.args[1]["amount"], 5605)
        self.assertEqual(post.call_args.args[1]["transaction_id"], info["provider_ref"])

    def test_create_without_url_raises(self):
        with mock.patch.object(CinetPayProvider, "_post", return_value={"code": "400", "data": {}}):
            with self.assertRaises(ProviderError):
                CinetPayProvider().create(self.payment, self.payment.order, self.buyer)

    def test_status_mapping(self):
        f = CinetPayProvider().fetch_status
        for reply, expected in [(self._check(), "succeeded"), (self._check("00", "REFUSED"), "failed"),
                                (self._check("662", "WAITING_FOR_CUSTOMER"), "pending"), (self._check("625", ""), "pending"),
                                (self._check(amount="100"), "failed")]:  # sous-paiement : jamais validé
            with mock.patch.object(CinetPayProvider, "_post", return_value=reply):
                self.assertEqual(f(self.payment), expected, reply)

    def test_webhook_form_is_not_trusted_and_confirms_via_check(self):
        self.client.force_authenticate(None)
        with mock.patch.object(CinetPayProvider, "_post", return_value=self._check("662", "WAITING_FOR_CUSTOMER")):
            r = self.client.post("/api/payments/webhook/cinetpay/", {"cpm_trans_id": "EKabc", "cpm_result": "00"})
        self.assertEqual(r.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")  # le formulaire dit « 00 », CinetPay dit « en attente »
        with mock.patch.object(CinetPayProvider, "_post", return_value=self._check()):
            self.client.post("/api/payments/webhook/cinetpay/", {"cpm_trans_id": "EKabc"})
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.order.status), ("succeeded", "paid"))

    def test_notify_url_answers_get_for_cinetpay_probe(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/payments/webhook/cinetpay/").status_code, 200)
