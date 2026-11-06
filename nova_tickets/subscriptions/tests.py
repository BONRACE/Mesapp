import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from payments.models import Transaction
from payments.services import apply_gateway_status
from subscriptions import services
from subscriptions.models import Subscription


def mk(role="organisateur", n=1):
    return User.objects.create_user(email=f"u{n}{role}@x.test", username=f"u{n}{role}", password="pw123456!", role=role, country="BJ")


class SubscriptionTests(TestCase):
    def setUp(self):
        self.orga = mk()
        self.client.force_login(self.orga)

    def pay(self):
        r = self.client.post(reverse("subscriptions:pay"), {"method": "mtn_bj", "phone": "0197000001"})
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]), fetch_redirect_response=False)
        return tx

    def test_page_shows_price_and_methods(self):
        r = self.client.get(reverse("subscriptions:index"))
        self.assertContains(r, "5")
        self.assertContains(r, "MTN MoMo")
        self.assertContains(r, "Moov Money")

    def test_page_lists_all_methods_of_country(self):
        r = self.client.get(reverse("subscriptions:index"))
        for label in ("MTN MoMo", "Moov Money", "Celtiis Cash", "Carte bancaire", "PayPal", "Virement bancaire"):
            self.assertContains(r, label)

    def test_catalog_has_universal_methods_everywhere(self):
        from core.payments import methods_for_country
        for code in ("BJ", "CI", "SN", "NG", "FR", "XX"):
            keys = {m["key"] for m in methods_for_country(code)}
            self.assertTrue({"card", "paypal"} <= keys, code)
            self.assertEqual(len([m for m in methods_for_country(code) if m["kind"] == "bank"]), 1, code)

    def test_other_methods_activate_immediately_and_email(self):
        from django.core import mail
        for key in ("card", "paypal", "bank", "celtiis_bj"):
            Subscription.objects.all().delete()
            mail.outbox.clear()
            with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.client.post(reverse("subscriptions:pay"), {"method": key, "phone": "0197000002"})
            self.assertTrue(services.is_active(self.orga), key)
            self.assertEqual(Subscription.objects.get().price, 5000)
            self.assertEqual(len(mail.outbox), 1, key)

    def test_simulated_failure_does_not_activate(self):
        self.client.post(reverse("subscriptions:pay"), {"method": "celtiis_bj", "phone": "0197000000"})
        self.assertFalse(services.is_active(self.orga))

    def test_method_outside_country_or_missing_phone_rejected(self):
        self.client.post(reverse("subscriptions:pay"), {"method": "wave_sn", "phone": "0197000001"})
        self.client.post(reverse("subscriptions:pay"), {"method": "mtn_bj", "phone": ""})
        self.assertEqual(Subscription.objects.count(), 0)

    def test_spectator_cannot_access(self):
        self.client.force_login(mk("spectateur", 2))
        self.assertRedirects(self.client.get(reverse("subscriptions:index")), reverse("orders:my_space"))

    def test_payment_amount_is_5000_and_activates_once(self):
        tx = self.pay()
        self.assertEqual(int(tx.amount), 5000)
        self.assertFalse(services.is_active(self.orga))
        apply_gateway_status(tx.reference, "APPROVED", gateway_reference="G1", amount=5000)
        self.assertTrue(services.is_active(self.orga))
        end = services.active_until(self.orga)
        apply_gateway_status(tx.reference, "APPROVED", gateway_reference="G1", amount=5000)  # rejeu
        self.assertEqual(services.active_until(self.orga), end)
        self.assertEqual(Subscription.objects.filter(is_paid=True).count(), 1)

    def test_failed_payment_does_not_activate(self):
        tx = self.pay()
        apply_gateway_status(tx.reference, "DECLINED")
        self.assertFalse(services.is_active(self.orga))

    def test_renewal_stacks(self):
        s1 = Subscription.objects.create(user=self.orga, price=5000, days=30)
        services.activate(s1)
        first_end = services.active_until(self.orga)
        s2 = Subscription.objects.create(user=self.orga, price=5000, days=30)
        services.activate(s2)
        self.assertEqual(services.active_until(self.orga), first_end + timedelta(days=30))

    def test_receipt_email_sent(self):
        from django.core import mail
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            with self.captureOnCommitCallbacks(execute=True):
                tx = self.pay()
                apply_gateway_status(tx.reference, "APPROVED", gateway_reference="G1", amount=5000)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(SUBSCRIPTION_REQUIRED=True)
    def test_required_blocks_event_creation_without_subscription(self):
        r = self.client.get(reverse("events:create"))
        self.assertRedirects(r, reverse("subscriptions:index"), fetch_redirect_response=False)
        services.activate(Subscription.objects.create(user=self.orga, price=5000, days=30))
        self.assertEqual(self.client.get(reverse("events:create")).status_code, 200)

    def test_not_required_by_default(self):
        self.assertEqual(self.client.get(reverse("events:create")).status_code, 200)

    def test_nav_and_dashboard_button_only_for_organizer(self):
        url = reverse("subscriptions:index")
        self.assertContains(self.client.get(reverse("events:orga_dashboard")), url)
        self.client.force_login(mk("spectateur", 3))
        self.assertNotContains(self.client.get("/"), url)


class CommissionWithSubscriptionTests(TestCase):
    """Abonnement actif = 0 % de commission ; sinon 2,5 %."""

    def setUp(self):
        from core.tests_security import event, user
        self.orga, self.fan = user("organisateur", 11), user("spectateur", 12)
        self.ev, self.tt = event(self.orga)

    def buy(self):
        from orders.services import create_order, finalize_order
        order = create_order(self.fan, self.tt, 2)
        order, _ = finalize_order(order, "mtn_bj", "MTN MoMo", "229", "R")
        order.refresh_from_db()
        return order

    def subscribe(self, days=30):
        services.activate(Subscription.objects.create(user=self.orga, price=5000, days=days))

    def test_without_subscription_commission_is_2_5_percent(self):
        o = self.buy()
        self.assertEqual((o.total, o.commission, o.organizer_amount), (20000, 500, 19500))

    def test_with_active_subscription_no_commission(self):
        self.subscribe()
        o = self.buy()
        self.assertEqual((o.total, o.commission, o.organizer_amount), (20000, 0, 20000))

    def test_expired_subscription_commission_returns(self):
        self.subscribe()
        Subscription.objects.update(ends_at=timezone.now() - timedelta(minutes=1))
        o = self.buy()
        self.assertEqual((o.commission, o.organizer_amount), (500, 19500))

    def test_commission_follows_subscription_at_payment_time(self):
        from orders.services import create_order, finalize_order
        order = create_order(self.fan, self.tt, 1)                  # créée sans abonnement : 250 prévus
        self.assertEqual(order.commission, 250)
        self.subscribe()                                           # l'organisateur s'abonne avant le paiement
        order, _ = finalize_order(order, "mtn_bj", "MTN MoMo", "229", "R")
        order.refresh_from_db()
        self.assertEqual((order.commission, order.organizer_amount), (0, 10000))

    def test_balance_and_dashboard_reflect_zero_commission(self):
        from orders.services import organizer_balance
        self.subscribe()
        self.buy()
        self.assertEqual(organizer_balance(self.orga), 20000)
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("events:orga_dashboard")), "0 % — abonné")

    def test_terms_and_subscription_page_mention_zero_commission(self):
        self.assertContains(self.client.get(reverse("core:terms")), "aucune commission")
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("subscriptions:index")), "0 % de commission")
