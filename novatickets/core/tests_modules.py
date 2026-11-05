"""Tests d'intégration des 6 modules : Mobile Money ↔ commandes, scanner, cartes, PDF, analytiques, retraits."""
import io
import json
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
from cards.models import BusinessCard
from cards.services import vcard
from events.models import Event, TicketType
from orders.models import Order, Ticket, Withdrawal
from orders.services import create_order, finalize_order, order_receipt_pdf, pay_order, tickets_pdf
from payments.models import Transaction
from payments.services import sign
from payouts.models import PayoutMethod
from scanner.models import ScanLog

TMP_MEDIA = tempfile.mkdtemp()
PW = "pw-test-1234"


def png(name="x.png"):
    buf = io.BytesIO()
    Image.new("RGB", (60, 60), (22, 163, 74)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP_MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   MOMO_WEBHOOK_SECRET="test-secret", MOMO_GATEWAY_MODE="simulation", BUSINESS_CARD_PRICE=100)
class ModulesBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        mk = lambda email, role, country, phone, **kw: User.objects.create_user(  # noqa: E731
            username=email, email=email, password=PW, role=role, country=country, phone=phone,
            first_name="Koffi", last_name="Dossou", sexe="M", **kw)
        self.orga = mk("o@t.test", "organisateur", "BJ", "+2290197000001", org_name="Orga Test")
        self.orga2 = mk("o2@t.test", "organisateur", "BJ", "+2290197000009", org_name="Orga Deux")
        self.fan = mk("f@t.test", "spectateur", "BJ", "+2290197000003")
        today = timezone.localdate()
        self.event = Event.objects.create(
            organizer=self.orga, name="Soirée Test", location="Cotonou", visual=png("v.png"),
            start_date=today + timedelta(days=10), end_date=today + timedelta(days=10), start_time=time(20, 0),
            purchase_deadline=today + timedelta(days=9), is_published=True)
        self.tt = TicketType.objects.create(event=self.event, name="Standard", price=10000, stock=5)

    def login(self, user):
        self.client.login(username=user.email, password=PW)

    def webhook(self, tx, status="APPROVED", amount=None):
        payload = {"reference": tx.reference, "status": status, "transaction_id": "OP-1"}
        if amount is not None:
            payload["amount"] = amount
        body = json.dumps(payload).encode()
        return self.client.post(reverse("payments:webhook"), data=body, content_type="application/json", HTTP_X_SIGNATURE=sign(body))

    def paid_order(self, qty=2, user=None):
        order = create_order(user or self.fan, self.tt, qty)
        pay_order(order, "card", "", send_email=False)
        order.refresh_from_db()
        return order


# ------------------------------------------------------------------ 1. Mobile Money ↔ commandes
class MobileMoneyOrderTests(ModulesBase):
    def start(self, qty=2):
        self.login(self.fan)
        self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": qty})
        order = Order.objects.get()
        r = self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "mtn_bj", "phone": "01 97 00 00 03"})
        return order, r

    def test_momo_creates_pending_transaction_without_tickets(self):
        order, r = self.start()
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]))
        self.assertEqual((tx.order_id, tx.provider, tx.status, int(tx.amount)), (order.pk, "MTN", "PENDING", 20000))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_page_reload_reuses_pending_transaction(self):
        order, _ = self.start()
        self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "mtn_bj", "phone": "01 97 00 00 03"})
        self.assertEqual(Transaction.objects.count(), 1)

    def test_webhook_success_finalizes_order_and_sends_one_receipt(self):
        order, _ = self.start()
        tx = Transaction.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.webhook(tx, amount=20000).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.payment_label, "MTN MoMo")
        self.assertEqual(Ticket.objects.filter(order=order).count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["f@t.test"])
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(tx, amount=20000)                      # rejeu de la notification
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_finalize_order_is_idempotent(self):
        order = create_order(self.fan, self.tt, 2)
        _, first = finalize_order(order, "momo_mtn", "MTN MoMo", "2290197000003", "OP-1")
        _, second = finalize_order(order, "momo_mtn", "MTN MoMo", "2290197000003", "OP-2")
        self.assertEqual((first, second), (True, False))
        self.assertEqual(Ticket.objects.filter(order=order).count(), 2)
        order.refresh_from_db()
        self.assertEqual(order.payment_ref, "OP-1")                  # le 2e appel ne réécrit rien

    def test_webhook_declined_leaves_order_pending(self):
        order, _ = self.start()
        self.webhook(Transaction.objects.get(), status="DECLINED")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(Transaction.objects.get().status, "FAILED")

    def test_wrong_amount_never_validates_order(self):
        order, _ = self.start()
        self.assertEqual(self.webhook(Transaction.objects.get(), amount=100).status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_failure_during_fulfilment_rolls_back_status_so_gateway_can_retry(self):
        from unittest import mock
        self.start()
        tx = Transaction.objects.get()
        with mock.patch("orders.services.finalize_order", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.webhook(tx)
        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")                    # pas de paiement « perdu »
        self.assertEqual(self.webhook(tx).status_code, 200)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_stock_sold_out_after_payment_flags_refund(self):
        order, _ = self.start(qty=2)
        other = User.objects.create_user(username="x@t.test", email="x@t.test", password=PW, country="BJ", phone="+2290197000044", first_name="A", last_name="B")
        big = create_order(other, self.tt, 4)
        pay_order(big, "card", "", send_email=False)               # 4 vendus : il n'en reste qu'1 pour une commande de 2
        self.webhook(Transaction.objects.get())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEEDS_REFUND)
        self.assertEqual(Ticket.objects.filter(order=order).count(), 0)
        self.assertEqual(self.client.get(reverse("payments:status", args=[Transaction.objects.get().pk])).status_code, 200)

    def test_organizer_cannot_pay_for_own_event(self):
        order = create_order(self.orga2, self.tt, 1)
        self.client.logout(); self.login(self.orga)
        self.assertEqual(self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "mtn_bj", "phone": "0197000001"}).status_code, 404)

    def test_card_payment_remains_simulated(self):
        self.login(self.fan)
        self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": 1})
        order = Order.objects.get()
        self.client.post(reverse("orders:pay", args=[order.reference]), {"method": "card", "phone": ""})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(Transaction.objects.count(), 0)


# ------------------------------------------------------------------ 2. Scanner
class ScannerTests(ModulesBase):
    def scan(self, code, event=None, source="camera"):
        r = self.client.post(reverse("scanner:api", args=[(event or self.event).pk]),
                             data=json.dumps({"code": code, "source": source}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_pages_render(self):
        self.paid_order()
        self.login(self.orga)
        self.assertContains(self.client.get(reverse("scanner:index")), "Soirée Test")
        r = self.client.get(reverse("scanner:scan", args=[self.event.pk]))
        self.assertContains(r, "html5-qrcode.min.js")
        self.assertContains(r, "Démarrer la caméra")

    def test_valid_then_duplicate(self):
        order = self.paid_order(qty=2)
        t = order.tickets.first()
        self.login(self.orga)
        first = self.scan(f"http://127.0.0.1:8000/verification/{t.reference}/")     # le QR contient l'URL complète
        self.assertEqual(first["result"], "valid")
        self.assertEqual(first["ticket"]["holder"], "DOSSOU Koffi")
        self.assertEqual((first["stats"]["checked_in"], first["stats"]["total"]), (1, 2))
        second = self.scan(t.reference)                                              # la référence seule marche aussi
        self.assertEqual(second["result"], "duplicate")
        self.assertEqual(ScanLog.objects.filter(result="valid").count(), 1)
        t.refresh_from_db()
        self.assertTrue(t.is_used)

    def test_invalid_codes(self):
        self.login(self.orga)
        for code in ("", "n'importe quoi", "TK-AAAAAAAAAA"):
            self.assertEqual(self.scan(code)["result"], "invalid")

    def test_unpaid_order_ticket_is_invalid(self):
        order = create_order(self.fan, self.tt, 1)
        t = Ticket.objects.create(order=order, reference="TK-ABCDEFGH23")
        self.login(self.orga)
        self.assertEqual(self.scan(t.reference)["result"], "invalid")

    def test_other_organizers_ticket_is_invalid_and_not_consumed(self):
        order = self.paid_order()
        t = order.tickets.first()
        self.login(self.orga2)
        other_event = Event.objects.create(
            organizer=self.orga2, name="Autre", location="X", visual=png("o.png"), start_date=timezone.localdate(),
            end_date=timezone.localdate(), start_time=time(10, 0), purchase_deadline=timezone.localdate(), is_published=True)
        self.assertEqual(self.scan(t.reference, event=other_event)["result"], "invalid")
        t.refresh_from_db()
        self.assertFalse(t.is_used)

    def test_ticket_for_another_event_of_same_organizer(self):
        order = self.paid_order()
        t = order.tickets.first()
        ev2 = Event.objects.create(
            organizer=self.orga, name="Event 2", location="X", visual=png("o.png"), start_date=timezone.localdate(),
            end_date=timezone.localdate(), start_time=time(10, 0), purchase_deadline=timezone.localdate(), is_published=True)
        self.login(self.orga)
        r = self.scan(t.reference, event=ev2)
        self.assertEqual(r["result"], "wrong_event")
        self.assertIn("Soirée Test", r["message"])
        t.refresh_from_db()
        self.assertFalse(t.is_used)

    def test_access_control(self):
        self.login(self.fan)
        self.assertEqual(self.client.get(reverse("scanner:index")).status_code, 302)
        self.assertEqual(self.client.post(reverse("scanner:api", args=[self.event.pk]), data="{}", content_type="application/json").status_code, 302)
        self.client.logout(); self.login(self.orga2)
        self.assertEqual(self.client.get(reverse("scanner:scan", args=[self.event.pk])).status_code, 404)

    def test_verify_link_also_logs_scan(self):
        t = self.paid_order().tickets.first()
        self.login(self.orga)
        self.client.post(reverse("core:verify", args=[t.reference]))
        self.assertEqual(ScanLog.objects.get().source, "link")
        t.refresh_from_db()
        self.assertTrue(t.is_used)

    def test_bad_json(self):
        self.login(self.orga)
        r = self.client.post(reverse("scanner:api", args=[self.event.pk]), data="pas json", content_type="application/json")
        self.assertEqual(r.status_code, 400)


# ------------------------------------------------------------------ 3. Cartes de visite
class BusinessCardTests(ModulesBase):
    def create_card(self, **extra):
        self.login(self.fan)
        data = {"full_name": "Koffi Marc Dossou", "job_title": "Développeur", "company": "Nova, Inc; Labs", "phone": "+229 01 97 00 00 03",
                "email": "koffi@pro.test", "website": "koffi.dev", "linkedin": "https://linkedin.com/in/koffi", "city": "Cotonou",
                "bio": "Je construis des produits.", "theme": "green", "show_on_ticket": "on"}
        data.update(extra)
        return self.client.post(reverse("cards:edit"), data)

    def test_create_prefills_and_saves(self):
        self.login(self.fan)
        r = self.client.get(reverse("cards:edit"))
        self.assertContains(r, "Koffi Dossou")                       # pré-rempli depuis le profil
        self.assertEqual(self.create_card().status_code, 302)
        card = BusinessCard.objects.get()
        self.assertEqual(card.user, self.fan)
        self.assertFalse(card.is_active)
        self.assertEqual(card.website, "https://koffi.dev")           # schéma ajouté

    def test_styles_and_colors(self):
        """Chaque couleur et chaque mise en page est acceptée, enregistrée et rendue (classes t-… l-…)."""
        self.create_card(theme="ocean", layout="split")
        card = BusinessCard.objects.get()
        self.assertEqual((card.theme, card.layout), ("ocean", "split"))
        self.assertContains(self.client.get(reverse("cards:public", args=[card.slug])), "vcard t-ocean l-split")
        for theme in BusinessCard.Theme.values:
            for layout in BusinessCard.Layout.values:
                self.assertEqual(self.client.post(reverse("cards:edit"), {
                    "full_name": "Koffi D", "theme": theme, "layout": layout, "show_on_ticket": "on"}).status_code, 302)
        card.refresh_from_db()
        self.assertEqual((card.theme, card.layout), (BusinessCard.Theme.values[-1], BusinessCard.Layout.values[-1]))

    def test_wax_layouts_recto_verso(self):
        """Styles « Pagne » : recto + verso dans la page, QR en couleur de palette uniquement une fois la carte activée."""
        self.create_card(theme="sunset", layout="wax")
        card = BusinessCard.objects.get()
        html = self.client.get(reverse("cards:public", args=[card.slug])).content.decode()
        for marker in ("l-wax", 'class="face front"', 'class="face back"', "Scannez-moi", "flipbtn", "QR code disponible après activation"):
            self.assertIn(marker, html)
        card.is_active = True
        card.save()
        html = self.client.get(reverse("cards:public", args=[card.slug])).content.decode()
        self.assertNotIn("QR code disponible après activation", html)
        self.assertEqual(self.client.get(reverse("cards:qr", args=[card.slug])).status_code, 200)

    def test_layout_optional_and_validated(self):
        self.create_card(theme="rose", layout="bold")
        self.create_card(theme="gold", layout="")                      # absent -> on garde le style actuel
        self.assertEqual(BusinessCard.objects.get().layout, "bold")
        self.assertEqual(BusinessCard.objects.get().theme, "gold")
        self.create_card(layout="n-importe-quoi")                      # refusé : rien n'est modifié
        self.assertEqual(BusinessCard.objects.get().theme, "gold")

    def test_invalid_linkedin_rejected(self):
        self.create_card(linkedin="https://exemple.com/koffi")
        self.assertFalse(BusinessCard.objects.exists())

    def test_inactive_card_is_private(self):
        self.create_card()
        card = BusinessCard.objects.get()
        self.assertContains(self.client.get(reverse("cards:public", args=[card.slug])), "Aperçu privé")   # propriétaire
        self.client.logout()
        for name in ("cards:public", "cards:vcard", "cards:qr"):
            self.assertEqual(self.client.get(reverse(name, args=[card.slug])).status_code, 404)

    def test_activation_by_mobile_money(self):
        self.create_card()
        card = BusinessCard.objects.get()
        r = self.client.post(reverse("cards:activate"), {"provider": "Moov", "phone": "01 96 00 00 05"})
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]))
        self.assertEqual((tx.business_card_id, int(tx.amount), tx.provider), (card.pk, 100, "Moov"))
        card.refresh_from_db()
        self.assertFalse(card.is_active)
        self.webhook(tx, amount=100)
        card.refresh_from_db()
        self.assertTrue(card.is_active)
        self.assertIsNotNone(card.activated_at)
        self.client.logout()                                          # maintenant publique
        self.assertContains(self.client.get(reverse("cards:public", args=[card.slug])), "Koffi Marc Dossou")
        self.assertEqual(self.client.get(reverse("cards:qr", args=[card.slug]))["Content-Type"], "image/png")

    @override_settings(BUSINESS_CARD_PRICE=0)
    def test_free_activation(self):
        self.create_card()
        self.client.post(reverse("cards:activate"))
        self.assertTrue(BusinessCard.objects.get().is_active)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_activation_requires_valid_payment_form(self):
        self.create_card()
        self.client.post(reverse("cards:activate"), {"provider": "Orange", "phone": "1"})
        self.assertEqual(Transaction.objects.count(), 0)

    def test_vcard_content_and_escaping(self):
        self.create_card()
        card = BusinessCard.objects.get()
        v = vcard(card)
        self.assertTrue(v.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n"))
        self.assertIn("FN:Koffi Marc Dossou", v)
        self.assertIn("N:Dossou;Koffi Marc;;;", v)
        self.assertIn(r"ORG:Nova\, Inc\; Labs", v)                  # , et ; échappés
        self.assertIn("TEL;TYPE=CELL,VOICE:+229 01 97 00 00 03", v)
        self.assertTrue(v.endswith("END:VCARD\r\n"))

    def test_ticket_page_links_to_card(self):
        t = self.paid_order().tickets.first()
        self.login(self.fan)
        self.assertContains(self.client.get(reverse("orders:ticket", args=[t.reference])), "Créer ma carte")
        self.create_card()
        self.assertContains(self.client.get(reverse("orders:ticket", args=[t.reference])), "Activer ma carte")
        BusinessCard.objects.update(is_active=True)
        r = self.client.get(reverse("orders:ticket", args=[t.reference]))
        self.assertContains(r, "Ouvrir ma carte")
        BusinessCard.objects.update(show_on_ticket=False)
        self.assertNotContains(self.client.get(reverse("orders:ticket", args=[t.reference])), "Ouvrir ma carte")


# ------------------------------------------------------------------ 4. PDF
class PdfTests(ModulesBase):
    def test_receipt_and_multi_ticket_pdfs(self):
        order = self.paid_order(qty=3)
        self.assertTrue(order_receipt_pdf(order).startswith(b"%PDF"))
        pdf = tickets_pdf(order.tickets.all())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(pdf.count(b"/Type /Page\n"), 3)             # un billet par page

    def test_download_endpoints_and_ownership(self):
        order = self.paid_order(qty=2)
        self.login(self.fan)
        for name in ("orders:receipt_pdf", "orders:order_tickets_pdf"):
            r = self.client.get(reverse(name, args=[order.reference]))
            self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
            self.assertIn("attachment", r["Content-Disposition"])
        self.client.logout(); self.login(self.orga2)
        self.assertEqual(self.client.get(reverse("orders:receipt_pdf", args=[order.reference])).status_code, 404)

    def test_pending_order_has_no_receipt(self):
        order = create_order(self.fan, self.tt, 1)
        self.login(self.fan)
        self.assertEqual(self.client.get(reverse("orders:receipt_pdf", args=[order.reference])).status_code, 404)

    def test_transaction_receipt_only_after_success(self):
        self.login(self.fan)
        self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": 1})
        self.client.post(reverse("orders:pay", args=[Order.objects.get().reference]), {"method": "mtn_bj", "phone": "0197000003"})
        tx = Transaction.objects.get()
        self.assertEqual(self.client.get(reverse("payments:receipt_pdf", args=[tx.pk])).status_code, 404)
        self.webhook(tx)
        r = self.client.get(reverse("payments:receipt_pdf", args=[tx.pk]))
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))

    def test_card_transaction_receipt(self):
        card = BusinessCard.objects.create(user=self.fan, full_name="K D")
        tx = Transaction.objects.create(user_email="f@t.test", phone_number="2290197000003", amount=100, provider="MTN",
                                        reference="NT-TEST-CARD", business_card=card, status="SUCCESS", paid_at=timezone.now())
        self.assertEqual(self.client.get(reverse("payments:receipt_pdf", args=[tx.pk])).status_code, 404)   # anonyme : refusé
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("payments:receipt_pdf", args=[tx.pk]))["Content-Type"], "application/pdf")


# ------------------------------------------------------------------ 5. Analytiques
class AnalyticsTests(ModulesBase):
    def test_numbers(self):
        order = self.paid_order(qty=3)                                # 30 000 brut, 750 commission (2,5 %), 29 250 net
        t = order.tickets.first()
        self.login(self.orga)
        self.client.post(reverse("scanner:api", args=[self.event.pk]), data=json.dumps({"code": t.reference}), content_type="application/json")
        self.client.post(reverse("scanner:api", args=[self.event.pk]), data=json.dumps({"code": t.reference}), content_type="application/json")
        self.client.post(reverse("scanner:api", args=[self.event.pk]), data=json.dumps({"code": "TK-ZZZZZZZZZZ"}), content_type="application/json")
        d = self.client.get(reverse("analytics:data")).json()
        k = d["kpi"]
        self.assertEqual((k["tickets"], k["gross"], k["commission"], k["net"], k["orders"]), (3, 30000, 750, 29250, 1))
        self.assertEqual((k["stock"], k["fill_rate"]), (5, 60.0))
        self.assertEqual((k["checked_in"], k["attendance_rate"], k["avg_order"]), (1, 33.3, 30000))
        self.assertEqual(len(d["daily"]), 30)
        self.assertEqual((d["daily"][-1]["tickets"], d["daily"][-1]["revenue"]), (3, 29250))
        self.assertEqual(sum(x["tickets"] for x in d["daily"]), 3)
        self.assertEqual(d["by_type"][0]["sold"], 3)
        self.assertEqual((d["scans"]["valid"], d["scans"]["duplicate"], d["scans"]["refused"]), (1, 1, 1))
        self.assertEqual(sum(h["count"] for h in d["scans"]["hourly"]), 1)
        self.assertEqual(len(d["recent_sales"]), 1)
        self.assertEqual(len(d["recent_scans"]), 3)

    def test_event_filter_and_isolation(self):
        self.paid_order(qty=2)
        self.login(self.orga2)                                        # un autre organisateur ne voit rien de l'événement
        d = self.client.get(reverse("analytics:data") + f"?event={self.event.pk}").json()
        self.assertEqual(d["kpi"]["tickets"], 0)
        self.client.logout(); self.login(self.orga)
        self.assertEqual(self.client.get(reverse("analytics:data") + f"?event={self.event.pk}").json()["kpi"]["tickets"], 2)

    def test_empty_dashboard(self):
        self.login(self.orga)
        d = self.client.get(reverse("analytics:data")).json()
        self.assertEqual((d["kpi"]["tickets"], d["kpi"]["fill_rate"], d["scans"]["hourly"]), (0, 0, []))
        self.assertContains(self.client.get(reverse("analytics:dashboard")), "chart.umd.js")

    def test_pending_and_refund_orders_excluded(self):
        create_order(self.fan, self.tt, 2)                            # non payée
        self.login(self.orga)
        self.assertEqual(self.client.get(reverse("analytics:data")).json()["kpi"]["tickets"], 0)

    def test_access_control(self):
        self.assertEqual(self.client.get(reverse("analytics:data")).status_code, 302)
        self.login(self.fan)
        self.assertEqual(self.client.get(reverse("analytics:dashboard")).status_code, 302)


# ------------------------------------------------------------------ 6. Moyens de retrait
class PayoutTests(ModulesBase):
    def add(self, **kw):
        data = {"kind": "mtn_momo", "label": "Perso", "account_holder": "Aïcha A.", "account_number": "01 97 00 00 01", "bank_name": "", "is_default": "on"}
        data.update(kw)
        return self.client.post(reverse("payouts:create"), data)

    def test_catalog_depends_on_country(self):
        from payouts.catalog import channels_for_country
        bj, sn = channels_for_country("BJ"), channels_for_country("SN")
        self.assertIn("celtiis_cash", bj); self.assertNotIn("wave", bj)
        self.assertIn("wave", sn); self.assertNotIn("celtiis_cash", sn)
        for c in (bj, sn, channels_for_country("FR")):
            self.assertIn("bank", c); self.assertIn("paypal", c)

    def test_add_mobile_money_bank_paypal(self):
        self.login(self.orga)
        self.assertEqual(self.add().status_code, 302)
        self.assertEqual(self.add(kind="bank", account_number="BJ66 0123 4567 8901", bank_name="Ecobank").status_code, 302)
        self.assertEqual(self.add(kind="paypal", account_number="Orga@PayPal.test", is_default="").status_code, 302)
        m = {x.kind: x for x in PayoutMethod.objects.all()}
        self.assertEqual(m["mtn_momo"].account_number, "+2290197000001")
        self.assertEqual(m["bank"].account_number, "BJ6601234567" "8901")
        self.assertEqual(m["paypal"].account_number, "orga@paypal.test")
        self.assertTrue(m["bank"].is_default and not m["mtn_momo"].is_default and not m["paypal"].is_default)   # un seul défaut
        self.assertEqual(m["mtn_momo"].display_account, "+229" + "•" * 8 + "01")
        self.assertEqual(m["bank"].display_account, "•••• 8901")
        self.assertEqual(m["paypal"].display_account, "o•••@paypal.test")
        self.assertNotIn("0197000001", m["mtn_momo"].display_account)

    def test_validation(self):
        self.login(self.orga)
        self.add(account_number="12")
        self.add(kind="bank", account_number="12", bank_name="")
        self.add(kind="paypal", account_number="pas-un-email")
        self.add(kind="wave")                                         # Wave n'existe pas au Bénin
        self.assertEqual(PayoutMethod.objects.count(), 0)

    def test_duplicate_rejected_and_limit(self):
        self.login(self.orga)
        self.add(); self.add()
        self.assertEqual(PayoutMethod.objects.count(), 1)
        for i in range(10):
            self.add(account_number=f"01 97 00 10 {i:02d}", is_default="")
        self.assertEqual(PayoutMethod.objects.count(), 8)

    def test_other_organizers_methods_are_inaccessible(self):
        m = PayoutMethod.objects.create(organizer=self.orga2, kind="mtn_momo", account_holder="X", account_number="+2290197000009")
        self.login(self.orga)
        self.assertEqual(self.client.get(reverse("payouts:edit", args=[m.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("payouts:delete", args=[m.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("payouts:default", args=[m.pk])).status_code, 404)

    def test_delete_default_promotes_another_and_keeps_history(self):
        self.login(self.orga)
        self.add(); self.add(kind="paypal", account_number="a@b.test", is_default="")
        mtn, pp = PayoutMethod.objects.get(kind="mtn_momo"), PayoutMethod.objects.get(kind="paypal")
        self.paid_order(qty=3)
        self.client.post(reverse("events:withdraw"), {"method": mtn.pk, "amount": "10000"})
        wd = Withdrawal.objects.get()
        self.assertEqual((wd.method_label, wd.amount), ("MTN MoMo", 10000))
        self.client.post(reverse("payouts:delete", args=[mtn.pk]))
        pp.refresh_from_db()
        self.assertTrue(pp.is_default)
        wd.refresh_from_db()
        self.assertIsNone(wd.payout_method)
        self.assertEqual(wd.method_label, "MTN MoMo")                 # l'historique garde son instantané
        self.assertContains(self.client.get(reverse("events:withdraw")), "MTN MoMo")

    def test_withdraw_page_requires_method(self):
        self.paid_order(qty=3)
        self.login(self.orga)
        self.assertContains(self.client.get(reverse("events:withdraw")), "Ajoutez d'abord un moyen de retrait")
        self.client.post(reverse("events:withdraw"), {"method": "", "amount": "5000"})
        self.assertEqual(Withdrawal.objects.count(), 0)

    def test_pages_render(self):
        self.login(self.orga)
        self.add()
        for name in ("payouts:list", "payouts:create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("payouts:edit", args=[PayoutMethod.objects.get().pk])).status_code, 200)


# ------------------------------------------------------------------ Mobile Money hors Bénin (zone FCFA)
class MobileMoneyOtherCountriesTests(ModulesBase):
    def buyer(self, country, phone, email="ci@t.test"):
        return User.objects.create_user(username=email, email=email, password=PW, role="spectateur", country=country,
                                        phone=phone, first_name="Fatou", last_name="Traoré", sexe="F")

    def pay(self, user, method, phone, qty=1):
        self.login(user)
        self.client.post(reverse("orders:checkout", args=[self.event.pk]), {"ticket_type": self.tt.pk, "quantity": qty})
        order = Order.objects.get(buyer=user)
        return order, self.client.post(reverse("orders:pay", args=[order.reference]), {"method": method, "phone": phone})

    def test_normalize_phone_by_country(self):
        from payments.services import PaymentError, normalize_phone
        self.assertEqual(normalize_phone("07 07 00 00 04", "CI"), "2250707000004")
        self.assertEqual(normalize_phone("+225 07 07 00 00 04", "CI"), "2250707000004")
        self.assertEqual(normalize_phone("90 00 00 06", "TG"), "22890000006")
        self.assertEqual(normalize_phone("0197000001"), "2290197000001")       # Bénin inchangé
        for bad, country in (("12", "CI"), ("", "TG"), ("abc", "BF")):
            with self.assertRaises(PaymentError):
                normalize_phone(bad, country)

    def test_ivory_coast_mtn_goes_through_push_and_webhook(self):
        fan = self.buyer("CI", "+2250707000004")
        order, r = self.pay(fan, "mtn_ci", "07 07 00 00 04")
        tx = Transaction.objects.get()
        self.assertRedirects(r, reverse("payments:status", args=[tx.pk]))
        self.assertEqual((tx.provider, tx.phone_number, tx.status, tx.order_id), ("MTN", "2250707000004", "PENDING", order.pk))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.webhook(tx, amount=10000).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(Ticket.objects.filter(order=order).count(), 1)

    def test_choice_and_phone_kept_after_invalid_number(self):
        fan = self.buyer("CI", "+2250707000004")
        _, r = self.pay(fan, "mtn_ci", "12")
        self.assertContains(r, 'value="mtn_ci" data-kind="momo" checked')     # pas re-sélectionné sur Orange Money
        self.assertContains(r, 'name="phone" value="12"')

    def test_togo_moov_uses_moov_provider(self):
        fan = self.buyer("TG", "+22890000006", email="tg@t.test")
        self.pay(fan, "moov_tg", "90 00 00 06")
        self.assertEqual(Transaction.objects.get().provider, "Moov")

    def test_invalid_number_creates_no_transaction(self):
        fan = self.buyer("CI", "+2250707000004")
        order, r = self.pay(fan, "mtn_ci", "12")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_other_currency_countries_stay_simulated(self):
        from core.payments import find_method
        self.assertIsNone(find_method("GH", "mtn_gh")["provider"])
        self.assertIsNone(find_method("CM", "mtn_cm")["provider"])
        self.assertEqual(find_method("CI", "moov_ci")["provider"], "Moov")


# ------------------------------------------------------------------ carte liée au billet
class CardTicketLinkTests(ModulesBase):
    def setUp(self):
        super().setUp()
        self.order = self.paid_order(qty=1)
        self.ticket = self.order.tickets.get()
        self.card = BusinessCard.objects.create(user=self.fan, full_name="Koffi Dossou", is_active=True)

    def test_badge_shown_for_own_paid_ticket(self):
        r = self.client.get(reverse("cards:public", args=[self.card.slug]) + f"?billet={self.ticket.reference}")
        self.assertContains(r, "Participant")
        self.assertContains(r, "Soirée Test")

    def test_no_badge_without_or_with_foreign_ticket(self):
        url = reverse("cards:public", args=[self.card.slug])
        self.assertNotContains(self.client.get(url), "Participant")
        other_order = create_order(self.orga2, self.tt, 1)
        pay_order(other_order, "card", "", send_email=False)
        foreign = other_order.tickets.get()
        self.assertNotContains(self.client.get(url + f"?billet={foreign.reference}"), "Participant")
        self.assertNotContains(self.client.get(url + "?billet=TK-ZZZZZZZZZZ"), "Participant")

    def test_inactive_card_never_shows_badge(self):
        self.card.is_active = False
        self.card.save()
        self.login(self.fan)
        r = self.client.get(reverse("cards:public", args=[self.card.slug]) + f"?billet={self.ticket.reference}")
        self.assertNotContains(r, "Participant")

    def test_ticket_page_links_card_to_ticket_and_qr_works(self):
        self.login(self.fan)
        r = self.client.get(reverse("orders:ticket", args=[self.ticket.reference]))
        self.assertContains(r, f"?billet={self.ticket.reference}")
        q = self.client.get(reverse("cards:qr", args=[self.card.slug]) + f"?billet={self.ticket.reference}")
        self.assertEqual((q.status_code, q["Content-Type"]), (200, "image/png"))


# ------------------------------------------------------------------ analytiques : noms de types
class AnalyticsNamesTests(ModulesBase):
    def test_by_type_separates_event_and_type_names(self):
        from analytics.services import build_stats
        all_events = build_stats(self.orga)["by_type"][0]
        self.assertEqual((all_events["name"], all_events["event"]), ("Standard", "Soirée Test"))
        one = build_stats(self.orga, event=self.event)["by_type"][0]
        self.assertEqual((one["name"], one["event"]), ("Standard", ""))


# ------------------------------------------------------------------ 7. Reçu (format maquette) + envoi automatique
class ReceiptFormatTests(ModulesBase):
    def test_email_follows_template(self):
        """E-mail de reçu : sections de la maquette, logo de la plateforme, signature, PDF joints, envoi automatique."""
        from django.core import mail
        from orders.services import create_order, pay_order

        self.orga.signature = "Adama Touré – Directeur"
        self.orga.signature_mode = "manager"
        self.orga.save()
        order = create_order(self.fan, self.tt, 2)
        pay_order(order, "mtn_bj", "+2290197000003")
        msg = mail.outbox[-1]
        html = msg.alternatives[0][0]
        for text in ("Plateforme de Billetterie", "Merci pour votre achat !", "Nom de l'événement", "Informations du spectateur",
                     "Détails du ticket", "Type de ticket payé", "Prix unitaire", "Quantité", "Statut du paiement", "Montant total",
                     "Signature de l'organisateur", "Adama Touré – Directeur", "Powered by"):
            self.assertIn(text, html)
        self.assertIn("cid:logo", html)
        self.assertEqual(len([a for a in msg.attachments if a[2] == "application/pdf"]), 3)

    def test_signature_falls_back_to_name(self):
        self.assertEqual(self.orga.signature_text, self.orga.display_name)

    def test_card_activation_sends_receipt(self):
        """Une activation de carte (sans commande) envoie aussi son reçu par e-mail."""
        from django.core import mail
        from payments.services import apply_gateway_status, create_transaction

        tx = create_transaction(user_email="f@t.test", phone_number="0197000003", amount=100, provider="MTN")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            apply_gateway_status(tx.reference, "SUCCESS")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Détails du paiement", mail.outbox[0].alternatives[0][0])
        self.assertEqual(mail.outbox[0].to, ["f@t.test"])


class CardCreationPreviewTests(ModulesBase):
    def test_new_user_sees_styles_preview_before_creating(self):
        """Sans carte enregistrée, la page de création montre déjà un aperçu pré-rempli et tous les styles."""
        self.login(self.fan)
        html = self.client.get(reverse("cards:edit")).content.decode()
        self.assertFalse(BusinessCard.objects.exists())
        self.assertIn('id="card-preview"', html)
        self.assertIn("Koffi Dossou", html)                      # aperçu pré-rempli depuis le profil
        for value in BusinessCard.Layout.values + BusinessCard.Theme.values:
            self.assertIn(f'value="{value}"', html)
        self.assertEqual(BusinessCard.objects.count(), 0)         # l'aperçu n'enregistre rien


class CardPdfTests(ModulesBase):
    def test_pdf_requires_activation_then_downloads(self):
        self.login(self.fan)
        self.client.post(reverse("cards:edit"), {"full_name": "Koffi D", "company": "Nova", "theme": "sunset", "layout": "wax", "show_on_ticket": "on"})
        card = BusinessCard.objects.get()
        r = self.client.get(reverse("cards:pdf"))
        self.assertRedirects(r, reverse("cards:edit"))                      # carte non payée : pas de PDF
        card.is_active = True
        card.save()
        r = self.client.get(reverse("cards:pdf"))
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn("inline", self.client.get(reverse("cards:pdf") + "?inline=1")["Content-Disposition"])   # pour l'impression
        self.assertEqual(r.content.count(b"/Type /Page\n"), 2)             # recto + verso
        card.layout = "waxtop"
        card.save()
        self.assertEqual(self.client.get(reverse("cards:pdf")).content.count(b"/Type /Page\n"), 1)   # verso seul

    def test_pdf_is_private(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("cards:pdf")).status_code, 302)           # connexion requise

    def test_buttons_shown_after_activation(self):
        self.login(self.fan)
        self.client.post(reverse("cards:edit"), {"full_name": "Koffi D", "theme": "green", "layout": "classic", "show_on_ticket": "on"})
        BusinessCard.objects.update(is_active=True)
        html = self.client.get(reverse("cards:edit")).content.decode()
        self.assertIn("Télécharger (PDF)", html)
        self.assertIn("data-print-pdf", html)


class ReceiptEmailEverywhereTests(ModulesBase):
    """Tout achat payé (billets OU carte de visite, par Mobile Money ou paiement simulé) => un e-mail de reçu automatique,
    avec le logo NovaTickets du projet et le reçu PDF."""

    def assertReceipt(self, msg, to, expected_pdfs):
        from pathlib import Path
        from django.conf import settings
        self.assertEqual(msg.to, [to])
        html = msg.alternatives[0][0]
        self.assertIn("cid:logo", html)
        logo = Path(settings.BASE_DIR, "static/img/logo-horizontal.png").read_bytes()
        cids = {p["Content-ID"]: p.get_payload(decode=True) for p in msg.message().walk() if p["Content-ID"]}   # images intégrées
        self.assertEqual(cids["<logo>"], logo)                              # c'est bien le logo fourni, pas un autre
        self.assertEqual(len([a for a in msg.attachments if a[2] == "application/pdf"]), expected_pdfs)

    def test_ticket_purchase_by_mobile_money_sends_receipt(self):
        from orders.services import start_mobile_money
        from core.payments import find_method
        order = create_order(self.fan, self.tt, 2)
        start_mobile_money(order, find_method("BJ", "mtn_bj"), "01 97 00 00 03", "http://x/webhook/")
        tx = Transaction.objects.get()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(tx, amount=20000)
        self.assertEqual(len(mail.outbox), 1)
        self.assertReceipt(mail.outbox[0], "f@t.test", expected_pdfs=3)     # reçu + 2 billets
        self.assertIn("Soirée Test", mail.outbox[0].alternatives[0][0])

    def test_card_purchase_by_mobile_money_sends_receipt(self):
        self.login(self.fan)
        self.client.post(reverse("cards:edit"), {"full_name": "Koffi D", "theme": "green", "layout": "classic", "show_on_ticket": "on"})
        self.client.post(reverse("cards:activate"), {"provider": "MTN", "phone": "01 97 00 00 03"})
        tx = Transaction.objects.get()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(tx, amount=100)
        self.assertTrue(BusinessCard.objects.get().is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertReceipt(mail.outbox[0], "f@t.test", expected_pdfs=1)
        self.assertIn("100 FCFA", mail.outbox[0].alternatives[0][0])

    def test_failed_payment_sends_no_receipt(self):
        self.login(self.fan)
        self.client.post(reverse("cards:edit"), {"full_name": "Koffi D", "theme": "green", "layout": "classic", "show_on_ticket": "on"})
        self.client.post(reverse("cards:activate"), {"provider": "MTN", "phone": "01 97 00 00 03"})
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(Transaction.objects.get(), status="DECLINED")
        self.assertEqual(len(mail.outbox), 0)


class BottomNavAndLegalTests(ModulesBase):
    def test_bottom_nav_everywhere(self):
        """La barre de navigation fixe est dans chaque page ; les entrées dépendent du rôle ; plus de bandeau haut."""
        anon = self.client.get(reverse("core:home")).content.decode()
        self.assertIn('class="bottombar"', anon)
        self.assertNotIn('<header class="nav">', anon)
        self.assertIn("Connexion", anon)
        self.assertIn("Créer un compte", anon)
        self.login(self.fan)
        fan = self.client.get(reverse("core:home")).content.decode()
        for label in ("Mes billets", "Ma carte", "Profil", "Déconnexion"):
            self.assertIn(label, fan)
        self.assertNotIn("Scanner", fan)
        self.client.logout()
        self.login(self.orga)
        orga = self.client.get(reverse("core:home")).content.decode()
        for label in ("Organisateur", "Analytiques", "Scanner"):
            self.assertIn(label, orga)

    def test_terms_cover_event_types_and_prohibitions(self):
        html = self.client.get(reverse("core:terms")).content.decode()
        for text in ("Concerts et spectacles", "Formations et ateliers", "Tous autres types d'événements", "SACEM", "BUBEDRA",
                     "Responsabilité exclusive de l'Organisateur", "incitant à la haine", "escroquerie", 'id="evenements"', 'href="#evenements"'):
            self.assertIn(text, html)

    def test_terms_page_covers_required_sections(self):
        r = self.client.get(reverse("core:terms"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for text in ("Objet du service", "Création et gestion du compte", "Achat de billets", "Revente, cession", "Paiements, frais de service",
                     "2,5 % du prix de chaque billet", "Responsabilité de la plateforme", "Protection des données personnelles",
                     "250", "9 750"):
            self.assertIn(text, html)
        self.assertContains(self.client.get(reverse("core:terms")), reverse("core:terms"))      # lien dans le pied de page

    def test_commission_text_matches_setting(self):
        self.assertContains(self.client.get(reverse("core:terms")), "Commission plateforme : 2,5 %")


class EnvLoaderTests(TestCase):
    def test_load_env_parses_file_and_never_overrides_system_values(self):
        import os, tempfile
        from config.env import env_bool, env_int, load_env
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write('# commentaire\nNT_A=valeur\nNT_B="avec espaces"\nNT_C=True  # fin de ligne\nNT_PORT=587\nNT_SYSTEM=depuis-fichier\n\nsans-egal\n')
        os.environ["NT_SYSTEM"] = "depuis-systeme"
        try:
            load_env(f.name)
            self.assertEqual((os.environ["NT_A"], os.environ["NT_B"]), ("valeur", "avec espaces"))
            self.assertTrue(env_bool("NT_C"))
            self.assertEqual(env_int("NT_PORT"), 587)
            self.assertEqual(os.environ["NT_SYSTEM"], "depuis-systeme")
        finally:
            for k in ("NT_A", "NT_B", "NT_C", "NT_PORT", "NT_SYSTEM"):
                os.environ.pop(k, None)
            os.unlink(f.name)

    def test_smtp_settings_exist(self):
        from django.conf import settings
        for name in ("EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "EMAIL_USE_TLS", "DEFAULT_FROM_EMAIL"):
            self.assertTrue(hasattr(settings, name), name)


class StaticVersioningTests(TestCase):
    def test_static_urls_carry_version(self):
        from django.templatetags.static import static
        self.assertRegex(static("css/app.css"), r"app\.css\?v=\d+")
