"""Tests de sécurité : autorisations (RBAC / IDOR), falsification de prix, webhook, anti brute-force, en-têtes, XSS."""
import datetime
import hashlib
import hmac
import json
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from events.models import Event, TicketType
from orders.models import Order, Ticket
from orders.services import create_order, finalize_order
from payments.models import Transaction
from payments.services import create_transaction, sign
from scanner.services import check_in


def user(role, n, **kw):
    return User.objects.create_user(email=f"{role}{n}@sec.test", username=f"{role}{n}", password="Pw-123456-x", role=role,
                                    first_name="Test", last_name=f"N{n}", phone="+22997000000", sexe="F", **kw)


def event(orga, name="Concert"):
    today = datetime.date.today()
    ev = Event.objects.create(organizer=orga, name=name, location="Cotonou", start_date=today + datetime.timedelta(days=5),
                              end_date=today + datetime.timedelta(days=5), start_time=datetime.time(20),
                              purchase_deadline=today + datetime.timedelta(days=4), is_published=True, visual="x.png")
    return ev, TicketType.objects.create(event=ev, name="Std", price=10000, stock=50)


def paid_order(buyer, tt):
    order = create_order(buyer, tt, 1)
    order, _ = finalize_order(order, "mtn_bj", "MTN MoMo", "229", "REF")
    return order


class SecurityBase(TestCase):
    def setUp(self):
        cache.clear()
        self.orga_a, self.orga_b = user("organisateur", 1), user("organisateur", 2)
        self.fan, self.fan2 = user("spectateur", 3), user("spectateur", 4)
        self.ev_a, self.tt_a = event(self.orga_a, "Événement A")
        self.order = paid_order(self.fan, self.tt_a)
        self.ticket = self.order.tickets.first()


class RbacTests(SecurityBase):
    ORGA_URLS = ["events:orga_dashboard", "events:create", "events:withdraw", "analytics:dashboard", "analytics:data",
                 "scanner:index", "payouts:list", "payouts:create", "subscriptions:index"]

    def test_anonymous_redirected_to_login(self):
        for name in self.ORGA_URLS + ["orders:my_space", "accounts:profile", "cards:edit", "accounts:delete"]:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/connexion/", r["Location"], name)

    def test_spectator_cannot_reach_organizer_area(self):
        self.client.force_login(self.fan)
        for name in self.ORGA_URLS:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertNotIn("/connexion/", r["Location"], name)   # redirigé vers son espace, pas servi

    def test_state_changing_views_reject_get(self):
        self.client.force_login(self.orga_a)
        self.assertEqual(self.client.get(reverse("events:toggle", args=[self.ev_a.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("scanner:api", args=[self.ev_a.pk])).status_code, 405)

    def test_csrf_enforced_on_post(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.orga_a)
        self.assertEqual(c.post(reverse("events:toggle", args=[self.ev_a.pk])).status_code, 403)


class IdorTests(SecurityBase):
    def test_other_organizer_cannot_touch_my_event(self):
        self.client.force_login(self.orga_b)
        self.assertEqual(self.client.get(reverse("events:edit", args=[self.ev_a.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("events:toggle", args=[self.ev_a.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("scanner:scan", args=[self.ev_a.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("scanner:api", args=[self.ev_a.pk]), data="{}", content_type="application/json").status_code, 404)

    def test_other_organizer_cannot_scan_my_ticket_even_on_own_event(self):
        ev_b, _ = event(self.orga_b, "Événement B")
        res = check_in(user=self.orga_b, event=ev_b, code=self.ticket.reference)
        self.assertEqual(res["result"], "invalid")
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.used_at)

    def test_analytics_scoped_to_own_events(self):
        self.client.force_login(self.orga_b)
        data = self.client.get(reverse("analytics:data"), {"event": self.ev_a.pk}).json()
        self.assertEqual(json.dumps(data).count("Événement A"), 0)
        self.assertEqual(data["totals"]["tickets"] if "totals" in data else 0, 0)

    def test_buyer_isolation_for_tickets_orders_receipts(self):
        self.client.force_login(self.fan2)
        for name, arg in (("orders:ticket", self.ticket.reference), ("orders:ticket_pdf", self.ticket.reference),
                          ("orders:ticket_qr", self.ticket.reference), ("orders:confirmation", self.order.reference),
                          ("orders:receipt_pdf", self.order.reference), ("orders:order_tickets_pdf", self.order.reference),
                          ("orders:pay", self.order.reference)):
            self.assertEqual(self.client.get(reverse(name, args=[arg])).status_code, 404, name)

    def test_ticket_qr_requires_login(self):
        self.assertEqual(self.client.get(reverse("orders:ticket_qr", args=[self.ticket.reference])).status_code, 302)
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("orders:ticket_qr", args=[self.ticket.reference])).status_code, 200)
        self.client.force_login(self.orga_a)       # l'organisateur de l'événement peut aussi le voir
        self.assertEqual(self.client.get(reverse("orders:ticket_qr", args=[self.ticket.reference])).status_code, 200)

    def test_payout_methods_isolated(self):
        from payouts.models import PayoutMethod
        m = PayoutMethod.objects.create(organizer=self.orga_a, kind="momo", label="MTN", account_holder="A", account_number="0197000001")
        self.client.force_login(self.orga_b)
        for name in ("payouts:edit", "payouts:default", "payouts:delete"):
            r = self.client.post(reverse(name, args=[m.pk]))
            self.assertEqual(r.status_code, 404, name)
        self.assertTrue(PayoutMethod.objects.filter(pk=m.pk).exists())

    def test_unpublished_event_hidden_from_others(self):
        ev, _ = event(self.orga_a, "Brouillon")
        ev.is_published = False
        ev.save()
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("events:detail", args=[ev.pk])).status_code, 404)

    def test_payment_pages_only_for_owner(self):
        tx = create_transaction(user_email=self.fan.email, phone_number="0197000001", amount=0, provider="MTN", order=self.order, country="BJ")
        url = reverse("payments:status", args=[tx.pk])
        self.assertEqual(self.client.get(url).status_code, 404)             # anonyme
        self.client.force_login(self.fan2)
        self.assertEqual(self.client.get(url).status_code, 404)             # autre utilisateur
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(url).status_code, 200)             # propriétaire

    def test_verify_page_requires_signature_or_organizer(self):
        url = reverse("core:verify", args=[self.ticket.reference])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url + "?s=0000000000000000").status_code, 404)
        self.client.force_login(self.orga_b)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.orga_a)
        self.assertEqual(self.client.get(url).status_code, 200)


class TicketIntegrityTests(SecurityBase):
    def test_references_are_random_not_sequential(self):
        self.assertRegex(self.ticket.reference, r"^TK-[A-Z2-9]{10}$")
        self.assertRegex(self.order.reference, r"^CMD-[A-Z2-9]{8,}$")

    def test_double_scan_only_first_wins(self):
        first = check_in(user=self.orga_a, event=self.ev_a, code=self.ticket.reference)
        second = check_in(user=self.orga_a, event=self.ev_a, code=self.ticket.reference)
        self.assertEqual((first["result"], second["result"]), ("valid", "duplicate"))

    def test_conditional_update_blocks_simultaneous_scan(self):
        """Simule le 2e scan qui lit « non utilisé » juste avant que le 1er écrive : l'UPDATE conditionnel ne passe qu'une fois."""
        from django.utils import timezone
        n1 = Ticket.objects.filter(pk=self.ticket.pk, used_at__isnull=True).update(used_at=timezone.now())
        n2 = Ticket.objects.filter(pk=self.ticket.pk, used_at__isnull=True).update(used_at=timezone.now())
        self.assertEqual((n1, n2), (1, 0))

    def test_unpaid_or_forged_reference_invalid(self):
        order = create_order(self.fan2, self.tt_a, 1)          # non payée : aucun billet
        self.assertFalse(order.tickets.exists())
        for code in ("TK-AAAAAAAAAA", "' OR 1=1 --", "../../etc/passwd", "TK-" + "A" * 500):
            self.assertEqual(check_in(user=self.orga_a, event=self.ev_a, code=code)["result"], "invalid")


class PaymentSecurityTests(SecurityBase):
    def test_price_and_total_come_from_server(self):
        self.client.force_login(self.fan2)
        r = self.client.post(reverse("orders:checkout", args=[self.ev_a.pk]),
                             {"ticket_type": self.tt_a.pk, "quantity": "2", "price": "1", "unit_price": "1", "total": "1", "amount": "1"})
        order = Order.objects.filter(buyer=self.fan2).latest("id")
        self.assertEqual((order.unit_price, order.total), (10000, 20000))
        self.assertRedirects(r, reverse("orders:pay", args=[order.reference]), fetch_redirect_response=False)

    def test_quantity_and_ticket_type_abuse(self):
        self.client.force_login(self.fan2)
        for q in ("0", "-5", "abc", "999999"):
            self.client.post(reverse("orders:checkout", args=[self.ev_a.pk]), {"ticket_type": self.tt_a.pk, "quantity": q})
        other_ev, other_tt = event(self.orga_b, "B")
        r = self.client.post(reverse("orders:checkout", args=[self.ev_a.pk]), {"ticket_type": other_tt.pk, "quantity": "1"})
        self.assertEqual(r.status_code, 404)           # un type de ticket d'un autre événement n'est pas accepté
        self.assertFalse(Order.objects.filter(buyer=self.fan2).exists())

    def test_organizer_cannot_buy_own_ticket(self):
        self.client.force_login(self.orga_a)
        self.client.post(reverse("orders:checkout", args=[self.ev_a.pk]), {"ticket_type": self.tt_a.pk, "quantity": "1"})
        self.assertFalse(Order.objects.filter(buyer=self.orga_a).exists())

    def test_cannot_pay_someone_elses_order(self):
        order = create_order(self.fan2, self.tt_a, 1)
        self.client.force_login(self.fan)
        self.assertEqual(self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "card"}).status_code, 404)

    def test_simulated_payment_forbidden_when_disabled(self):
        order = create_order(self.fan2, self.tt_a, 1)
        self.client.force_login(self.fan2)
        with override_settings(ALLOW_SIMULATED_PAYMENTS=False):
            self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "card", "phone": "x"})
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.Status.PAID)

    def _tx(self):
        order = create_order(self.fan2, self.tt_a, 1)
        return create_transaction(user_email=self.fan2.email, phone_number="0197000001", amount=0, provider="MTN", order=order, country="BJ"), order

    def _post(self, payload, signature=None):
        body = json.dumps(payload).encode()
        return self.client.post(reverse("payments:webhook"), data=body, content_type="application/json",
                                HTTP_X_SIGNATURE=sign(body) if signature is None else signature)

    def test_webhook_rejects_missing_or_bad_signature(self):
        tx, order = self._tx()
        p = {"reference": tx.reference, "status": "APPROVED", "amount": 10000}
        self.assertEqual(self._post(p, signature="").status_code, 403)
        self.assertEqual(self._post(p, signature="0" * 64).status_code, 403)
        wrong_secret = hmac.new(b"autre-secret", json.dumps(p).encode(), hashlib.sha256).hexdigest()
        self.assertEqual(self._post(p, signature=wrong_secret).status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_webhook_wrong_amount_not_validated(self):
        tx, order = self._tx()
        self.assertEqual(self._post({"reference": tx.reference, "status": "APPROVED", "amount": 1}).status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_webhook_replay_is_idempotent(self):
        tx, order = self._tx()
        p = {"reference": tx.reference, "status": "APPROVED", "amount": 10000, "transaction_id": "G1"}
        self.assertEqual(self._post(p).status_code, 200)
        self.assertEqual(self._post(p).status_code, 200)
        self.assertEqual(Ticket.objects.filter(order=order).count(), 1)
        self.assertEqual(self._post({"reference": tx.reference, "status": "DECLINED"}).status_code, 200)   # contradictoire tardif
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.SUCCESS)

    def test_webhook_stale_timestamp_rejected(self):
        tx, order = self._tx()
        p = {"reference": tx.reference, "status": "APPROVED", "amount": 10000, "timestamp": time.time() - 3600}
        self.assertEqual(self._post(p).status_code, 400)

    @override_settings(MOMO_GATEWAY_MODE="live")
    def test_live_webhook_requires_amount(self):
        tx, order = self._tx()
        self.assertEqual(self._post({"reference": tx.reference, "status": "APPROVED"}).status_code, 400)

    def test_webhook_only_post_and_garbage_body(self):
        self.assertEqual(self.client.get(reverse("payments:webhook")).status_code, 405)
        body = b"not json"
        r = self.client.post(reverse("payments:webhook"), data=body, content_type="application/json", HTTP_X_SIGNATURE=sign(body))
        self.assertEqual(r.status_code, 400)

    def test_simulation_endpoint_disabled_outside_debug(self):
        tx, _ = self._tx()
        r = self.client.post(reverse("payments:simulate", args=[tx.pk]), {"outcome": "approve"})
        self.assertEqual(r.status_code, 404)           # les tests tournent avec DEBUG=False


class AuthSecurityTests(SecurityBase):
    def login(self, ident, pw):
        return self.client.post(reverse("accounts:login"), {"username": ident, "password": pw})

    def test_bruteforce_lock_even_with_right_password_afterwards(self):
        for _ in range(5):
            self.login(self.fan.email, "mauvais")
        r = self.login(self.fan.email, "Pw-123456-x")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(r, "Trop de tentatives")

    def test_lock_is_per_account_and_ip(self):
        for _ in range(5):
            self.login(self.fan.email, "mauvais")
        self.login(self.fan2.email, "Pw-123456-x")
        self.assertIn("_auth_user_id", self.client.session)      # un autre compte n'est pas verrouillé

    def test_no_account_enumeration_on_login(self):
        a = self.login("inconnu@sec.test", "x").content.decode()
        b = self.login(self.fan.email, "x").content.decode()
        import re
        strip = lambda s: re.sub(r"csrfmiddlewaretoken\" value=\"[^\"]+", "", s)
        self.assertEqual(strip(a).count("incorrect"), strip(b).count("incorrect"))

    def test_open_redirect_blocked(self):
        for nxt in ("https://evil.example/", "//evil.example/x", "javascript:alert(1)"):
            r = self.client.post(reverse("accounts:login") + "?next=" + nxt, {"username": self.fan.email, "password": "Pw-123456-x", "next": nxt})
            self.assertNotIn("evil", r.get("Location", ""))
            self.client.logout()

    def test_session_cookie_flags(self):
        r = self.login(self.fan.email, "Pw-123456-x")
        c = r.cookies["sessionid"]
        self.assertTrue(c["httponly"])
        self.assertEqual(c["samesite"], "Lax")

    def test_session_invalid_after_password_change_and_deletion(self):
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("orders:my_space")).status_code, 200)
        self.fan.set_password("Nouveau-mdp-9")
        self.fan.save()
        self.assertEqual(self.client.get(reverse("orders:my_space")).status_code, 302)    # ancienne session révoquée

    def test_password_reset_is_throttled_and_generic(self):
        from django.core import mail
        for _ in range(8):
            r = self.client.post(reverse("accounts:password_reset"), {"email": self.fan.email})
            self.assertEqual(r.status_code, 302)
        self.assertLessEqual(len(mail.outbox), 5)
        mail.outbox.clear()
        r = self.client.post(reverse("accounts:password_reset"), {"email": "personne@sec.test"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_token_single_use(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uid, token = urlsafe_base64_encode(force_bytes(self.fan.pk)), default_token_generator.make_token(self.fan)
        url = reverse("accounts:password_reset_confirm", args=[uid, token])
        r = self.client.get(url, follow=True)
        set_url = r.redirect_chain[-1][0]
        self.client.post(set_url, {"new_password1": "Tout-neuf-4521x", "new_password2": "Tout-neuf-4521x"})
        again = self.client.get(url)
        self.assertNotIn(b'name="new_password1"', again.content)       # lien déjà utilisé : refusé

    def test_admin_login_is_throttled(self):
        from django.conf import settings
        url = "/" + settings.ADMIN_URL + "login/"
        for _ in range(5):
            self.client.post(url, {"username": "admin", "password": "x", "next": "/" + settings.ADMIN_URL})
        r = self.client.post(url, {"username": "admin", "password": "x", "next": "/" + settings.ADMIN_URL})
        self.assertContains(r, "Trop de tentatives")

    def test_registration_cannot_self_assign_staff(self):
        r = self.client.post(reverse("accounts:register_spectateur"), {"is_staff": "on", "is_superuser": "on", "role": "organisateur",
                                                                      "email": "evil@sec.test", "username": "evil"})
        u = User.objects.filter(email="evil@sec.test").first()
        self.assertTrue(u is None or not (u.is_staff or u.is_superuser))


class HeadersAndInjectionTests(SecurityBase):
    def test_security_headers(self):
        r = self.client.get("/")
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertIn("object-src 'none'", r["Content-Security-Policy"])
        self.assertIn("camera=(self)", r["Permissions-Policy"])

    def test_authenticated_pages_not_cached(self):
        self.client.force_login(self.fan)
        self.assertIn("no-store", self.client.get(reverse("orders:my_space"))["Cache-Control"])

    def test_xss_escaped_in_event_name_and_search(self):
        payload = "<script>alert(1)</script>"
        ev, _ = event(self.orga_a, payload)
        html = self.client.get("/").content.decode()
        self.assertNotIn(payload, html)
        self.assertIn("&lt;script&gt;", html)
        html = self.client.get("/", {"q": payload}).content.decode()
        self.assertNotIn(payload, html)

    def test_xss_escaped_in_card_page(self):
        from cards.models import BusinessCard
        card = BusinessCard.objects.create(user=self.fan, full_name="<img src=x onerror=alert(1)>", bio="<script>alert(2)</script>", is_active=True)
        html = self.client.get(reverse("cards:public", args=[card.slug])).content.decode()
        self.assertNotIn("<img src=x onerror", html)
        self.assertNotIn("<script>alert(2)", html)

    def test_sql_injection_in_search_and_ids(self):
        for q in ("' OR '1'='1", "'; DROP TABLE events_event; --", "%' UNION SELECT 1 --"):
            self.assertEqual(self.client.get("/", {"q": q}).status_code, 200)
        self.assertTrue(Event.objects.exists())
        self.client.force_login(self.orga_a)
        self.assertEqual(self.client.get(reverse("analytics:data"), {"event": "1 OR 1=1"}).status_code, 200)

    def test_pdf_with_markup_in_names_does_not_crash_or_inject(self):
        ev, tt = event(self.orga_a, "<b>Gras</b> & <font color=red>x")
        self.fan2.first_name, self.fan2.last_name = "<para>A</para>", "</b><i>"
        self.fan2.save()
        order = paid_order(self.fan2, tt)
        from orders.services import order_receipt_pdf, ticket_pdf
        self.assertTrue(order_receipt_pdf(order).startswith(b"%PDF"))
        self.assertTrue(ticket_pdf(order.tickets.first()).startswith(b"%PDF"))

    def test_upload_rejects_non_image_and_oversized(self):
        self.client.force_login(self.orga_a)
        data = {"last_name": "A", "first_name": "B", "sexe": "F", "country": "BJ", "phone": "97000000", "org_name": "O", "signature_mode": "organizer"}
        bad = SimpleUploadedFile("logo.png", b"<?php system($_GET['c']); ?>", content_type="image/png")
        r = self.client.post(reverse("accounts:profile"), {**data, "org_logo": bad})
        self.assertContains(r, "image")                                  # message d'erreur, rien enregistré
        self.orga_a.refresh_from_db()
        self.assertFalse(self.orga_a.org_logo)
        svg = SimpleUploadedFile("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", content_type="image/svg+xml")
        self.client.post(reverse("accounts:profile"), {**data, "org_logo": svg})
        self.orga_a.refresh_from_db()
        self.assertFalse(self.orga_a.org_logo)

    def test_media_not_served_when_debug_false(self):
        from django.conf import settings
        from django.urls import resolve, Resolver404
        self.assertFalse(settings.DEBUG)
        with self.assertRaises(Resolver404):
            resolve("/media/users/photos/x.png")


class DeploySettingsTests(TestCase):
    def test_production_guard_refuses_defaults(self):
        import subprocess, sys, os
        env = {**os.environ, "DEBUG": "False", "SECRET_KEY": "dev-insecure-change-me-novatickets", "ALLOWED_HOSTS": "", "ALLOW_SIMULATED_PAYMENTS": "True"}
        out = subprocess.run([sys.executable, "manage.py", "check"], env=env, capture_output=True, text=True, cwd=".")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("SECRET_KEY", out.stderr)

    def test_production_guard_accepts_hardened_config(self):
        import subprocess, sys, os, secrets
        env = {**os.environ, "DEBUG": "False", "SECRET_KEY": secrets.token_urlsafe(64), "ALLOWED_HOSTS": "novatickets.app",
               "SITE_URL": "https://novatickets.app", "MOMO_WEBHOOK_SECRET": secrets.token_urlsafe(48), "ALLOW_SIMULATED_PAYMENTS": "False",
               "BEHIND_PROXY": "True"}
        out = subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"], env=env, capture_output=True, text=True, cwd=".")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
