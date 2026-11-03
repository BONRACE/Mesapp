import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Transaction
from .services import (
    PaymentError, apply_gateway_status, create_transaction, normalize_phone, parse_amount, sign,
)

SECRET = {"MOMO_WEBHOOK_SECRET": "test-secret", "MOMO_GATEWAY_MODE": "simulation"}


def make_tx(**kw):
    data = dict(user_email="a@b.test", phone_number="0197000001", amount=15000, provider="MTN")
    data.update(kw)
    return create_transaction(**data)


@override_settings(**SECRET)
class ServiceTests(TestCase):
    def test_phone_normalisation(self):
        for raw in ("0197000001", "01 97 00 00 01", "+229 01 97 00 00 01", "00229 0197000001", "97000001"):
            self.assertEqual(normalize_phone(raw), "2290197000001", raw)
        for bad in ("", "123", "0297000001", "abcdefghij"):
            with self.assertRaises(PaymentError):
                normalize_phone(bad)

    def test_amount_rules(self):
        self.assertEqual(parse_amount("15000"), Decimal("15000"))
        for bad in ("abc", "50", "-10", "99999999"):
            with self.assertRaises(PaymentError):
                parse_amount(bad)

    def test_create_transaction_is_pending_with_unique_reference(self):
        a, b = make_tx(), make_tx()
        self.assertEqual(a.status, "PENDING")
        self.assertNotEqual(a.reference, b.reference)
        self.assertTrue(a.reference.startswith("NT-"))
        self.assertEqual(a.phone_number, "2290197000001")
        self.assertEqual(a.user_email, "a@b.test")

    def test_unknown_provider_rejected(self):
        with self.assertRaises(PaymentError):
            make_tx(provider="Orange")

    def test_status_mapping(self):
        for raw, expected in (("APPROVED", "SUCCESS"), ("success", "SUCCESS"), ("DECLINED", "FAILED"),
                              ("cancelled", "FAILED"), ("FAILED", "FAILED")):
            tx = make_tx()
            self.assertEqual(apply_gateway_status(tx.reference, raw)[0].status, expected, raw)
        tx = make_tx()
        with self.assertRaises(PaymentError):
            apply_gateway_status(tx.reference, "PROCESSING")      # statut inconnu : on ne touche à rien
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")

    def test_final_state_is_never_overwritten(self):
        tx = make_tx()
        apply_gateway_status(tx.reference, "APPROVED")
        _, changed = apply_gateway_status(tx.reference, "DECLINED")   # notification contradictoire tardive
        tx.refresh_from_db()
        self.assertFalse(changed)
        self.assertEqual(tx.status, "SUCCESS")

    def test_success_hook_called_once(self):
        tx = make_tx()
        with mock.patch("payments.services.on_payment_success") as hook:
            apply_gateway_status(tx.reference, "APPROVED")
            apply_gateway_status(tx.reference, "APPROVED")            # rejeu
        self.assertEqual(hook.call_count, 1)

    def test_amount_mismatch_is_not_validated(self):
        tx = make_tx(amount=15000)
        with self.assertRaises(PaymentError):
            apply_gateway_status(tx.reference, "APPROVED", amount=100)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")
        apply_gateway_status(tx.reference, "APPROVED", amount=15000)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "SUCCESS")
        self.assertIsNotNone(tx.paid_at)


@override_settings(**SECRET)
class WebhookTests(TestCase):
    def post(self, payload, signature="auto"):
        body = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
        headers = {} if signature is None else {"HTTP_X_SIGNATURE": sign(body) if signature == "auto" else signature}
        return self.client.post(reverse("payments:webhook"), data=body, content_type="application/json", **headers)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("payments:webhook")).status_code, 405)

    def test_works_without_csrf_token(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        tx = make_tx()
        body = json.dumps({"reference": tx.reference, "status": "APPROVED"}).encode()
        r = c.post(reverse("payments:webhook"), data=body, content_type="application/json", HTTP_X_SIGNATURE=sign(body))
        self.assertEqual(r.status_code, 200)

    def test_missing_or_bad_signature_rejected(self):
        tx = make_tx()
        p = {"reference": tx.reference, "status": "APPROVED"}
        self.assertEqual(self.post(p, signature=None).status_code, 403)
        self.assertEqual(self.post(p, signature="deadbeef").status_code, 403)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")

    @override_settings(MOMO_WEBHOOK_SECRET="")
    def test_empty_secret_refuses_everything(self):
        tx = make_tx()
        body = json.dumps({"reference": tx.reference, "status": "APPROVED"}).encode()
        r = self.client.post(reverse("payments:webhook"), data=body, content_type="application/json", HTTP_X_SIGNATURE=sign(body))
        self.assertEqual(r.status_code, 403)

    def test_approved_and_declined(self):
        ok, ko = make_tx(), make_tx()
        self.assertEqual(self.post({"reference": ok.reference, "status": "APPROVED", "transaction_id": "G1", "amount": 15000}).status_code, 200)
        self.assertEqual(self.post({"reference": ko.reference, "status": "CANCELLED", "reason": "Annulé par le client"}).status_code, 200)
        ok.refresh_from_db(); ko.refresh_from_db()
        self.assertEqual((ok.status, ok.gateway_reference), ("SUCCESS", "G1"))
        self.assertEqual((ko.status, ko.failure_reason), ("FAILED", "Annulé par le client"))

    def test_replay_returns_200_without_change(self):
        tx = make_tx()
        p = {"reference": tx.reference, "status": "APPROVED"}
        self.assertEqual(self.post(p).json()["updated"], True)
        self.assertEqual(self.post(p).json()["updated"], False)

    def test_bad_inputs(self):
        self.assertEqual(self.post(b"pas du json").status_code, 400)
        self.assertEqual(self.post({"status": "APPROVED"}).status_code, 400)
        self.assertEqual(self.post({"reference": "NT-INCONNU", "status": "APPROVED"}).status_code, 404)
        tx = make_tx()
        self.assertEqual(self.post({"reference": tx.reference, "status": "???"}).status_code, 400)


@override_settings(**SECRET, DEBUG=True)
class ViewTests(TestCase):
    form = {"user_email": "Client@Test.COM", "provider": "MOOV".title(), "phone_number": "01 96 00 00 02", "amount": "20000"}

    def test_initiate_page_renders(self):
        r = self.client.get(reverse("payments:initiate"))
        self.assertContains(r, "MTN MoMo")
        self.assertContains(r, "Moov Money")

    def test_initiate_creates_pending_and_redirects_to_status(self):
        r = self.client.post(reverse("payments:initiate"), self.form)
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]))
        self.assertEqual((tx.status, tx.provider, tx.phone_number, tx.user_email), ("PENDING", "Moov", "2290196000002", "client@test.com"))
        self.assertTrue(tx.gateway_reference.startswith("SIM-"))

    def test_invalid_form_creates_nothing(self):
        for patch in ({"phone_number": "12"}, {"provider": "Orange"}, {"amount": "5"}, {"user_email": "x"}):
            r = self.client.post(reverse("payments:initiate"), {**self.form, **patch})
            self.assertEqual(r.status_code, 200, patch)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_gateway_down_marks_failed(self):
        with override_settings(MOMO_GATEWAY_MODE="live", MOMO_API_BASE_URL="http://127.0.0.1:9"):
            r = self.client.post(reverse("payments:initiate"), self.form)
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]))
        self.assertEqual(tx.status, "FAILED")

    def test_status_pending_success_failed(self):
        tx = make_tx()
        url = reverse("payments:status", args=[tx.pk])
        r = self.client.get(url)
        self.assertContains(r, "En attente de votre validation")
        self.assertContains(r, 'http-equiv="refresh"')
        self.assertNotContains(r, "Quittance")

        apply_gateway_status(tx.reference, "APPROVED", gateway_reference="OP-123")
        r = self.client.get(url)
        self.assertContains(r, "Paiement réussi")
        self.assertContains(r, "Quittance de paiement")
        self.assertContains(r, tx.reference)
        self.assertContains(r, "15\u00a0000 FCFA")
        self.assertContains(r, "OP-123")
        self.assertNotContains(r, "0197000001")        # numéro masqué sur le reçu
        self.assertNotContains(r, 'http-equiv="refresh"')

        ko = make_tx()
        apply_gateway_status(ko.reference, "DECLINED")
        r = self.client.get(reverse("payments:status", args=[ko.pk]))
        self.assertContains(r, "Paiement non abouti")
        self.assertNotContains(r, "Quittance")

    def test_unknown_uuid_404(self):
        self.assertEqual(self.client.get(reverse("payments:status", args=["11111111-2222-3333-4444-555555555555"])).status_code, 404)

    def test_full_flow_with_simulation_buttons(self):
        self.client.post(reverse("payments:initiate"), self.form)
        tx = Transaction.objects.get()
        r = self.client.post(reverse("payments:simulate", args=[tx.pk]), {"outcome": "approve"}, follow=True)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "SUCCESS")
        self.assertContains(r, "Quittance de paiement")

    @override_settings(DEBUG=False)
    def test_simulation_disabled_in_production(self):
        tx = make_tx()
        self.assertEqual(self.client.post(reverse("payments:simulate", args=[tx.pk]), {"outcome": "approve"}).status_code, 404)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")

    def test_status_json(self):
        tx = make_tx()
        self.assertEqual(self.client.get(reverse("payments:status_json", args=[tx.pk])).json()["status"], "PENDING")
