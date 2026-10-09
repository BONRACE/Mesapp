from datetime import date, time, timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse

import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from accounts.models import User
from core.models import BusinessCard
from events.models import Event, TicketType
from orders.models import Order, Ticket


def png_file(name="x.png", color=(200, 60, 60)):
    buf = BytesIO()
    Image.new("RGB", (60, 60), color).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


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


FRIEND = {"for_friend": "on", "friend_last_name": "Dossou", "friend_first_name": "Ami", "friend_sexe": "M",
          "friend_email": "ami@t.test", "friend_phone": "+229 96 00 00 11"}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FriendTicketTests(TestCase):
    """Réservation d'un billet pour un ami (spectateur ET organisateur)."""

    def setUp(self):
        self.orga = make_user("orga", User.ORGANISATEUR, org_name="Orga Prod")
        self.orga2 = make_user("orga2", User.ORGANISATEUR, org_name="Other")
        self.spec = make_user("spec", User.SPECTATEUR)
        d = date.today() + timedelta(days=5)
        self.event = Event.objects.create(organizer=self.orga, name="Show", start_date=d, end_date=d,
                                          start_time=time(19, 0), sales_deadline=d, status=Event.PUBLISHED)
        self.tt = TicketType.objects.create(event=self.event, name="VIP", price=10000, stock=20)

    def _buy(self, user, qty=1, **extra):
        self.client.force_login(user)
        return self.client.post(reverse("orders:buy", args=[self.event.slug]),
                                {"ticket_type": self.tt.pk, "quantity": qty, **extra})

    def _pay(self):
        order = Order.objects.latest("id")
        self.client.post(reverse("orders:pay", args=[order.reference]),
                         {"payment_method": "MTN Mobile Money", "payment_phone": "97000001"})
        order.refresh_from_db()
        return order

    def test_ticket_is_in_the_friends_name_and_friend_gets_the_pdf(self):
        self._buy(self.spec, qty=2, friend_photo=png_file(), **FRIEND)
        order = self._pay()
        self.assertEqual(order.status, Order.PAID)
        self.assertTrue(order.for_friend)
        self.assertEqual(order.holder_name, "Ami Dossou")
        # 2 e-mails : reçu à l'acheteur, billets PDF à l'ami
        self.assertEqual([m.to for m in mail.outbox], [["spec@t.test"], ["ami@t.test"]])
        pdfs = [a for a in mail.outbox[1].attachments if isinstance(a, tuple) and a[2] == "application/pdf"]
        self.assertEqual(len(pdfs), 2)
        self.assertTrue(pdfs[0][1].startswith(b"%PDF"))
        self.assertIn("Billet offert à", mail.outbox[0].body)
        # la page du billet et la page de contrôle montrent l'ami
        t = order.tickets.first()
        self.assertContains(self.client.get(t.get_absolute_url()), "DOSSOU")
        v = self.client.get(reverse("orders:verify", args=[t.code]))
        self.assertContains(v, "Ami Dossou")
        self.assertContains(v, "Offert par")
        self.assertContains(self.client.get(reverse("core:spectateur_dashboard")), "Offert à Ami Dossou")
        pdf = self.client.get(reverse("orders:ticket_pdf", args=[t.code]))
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))

    def test_friend_without_email_sends_only_the_receipt(self):
        self._buy(self.spec, **{**FRIEND, "friend_email": ""})
        self._pay()
        self.assertEqual(len(mail.outbox), 1)

    def test_friend_name_is_required(self):
        self._buy(self.spec, **{**FRIEND, "friend_last_name": ""})
        self.assertEqual(Order.objects.count(), 0)

    def test_normal_purchase_is_unchanged(self):
        self._buy(self.spec)
        order = self._pay()
        self.assertFalse(order.for_friend)
        self.assertEqual(order.holder_name, "Test SPEC")
        self.assertEqual(len(mail.outbox), 1)

    def test_organizer_can_book_for_a_friend_and_sees_his_tickets(self):
        self._buy(self.orga2, **FRIEND)
        order = self._pay()
        self.assertEqual(order.status, Order.PAID)
        page = self.client.get(reverse("core:spectateur_dashboard"))
        self.assertEqual(page.status_code, 200)       # plus de redirection pour les organisateurs
        self.assertContains(page, "Offert à Ami Dossou")
        # mais toujours pas pour son propre événement, même pour un ami
        self._buy(self.orga, **FRIEND)
        self.assertEqual(Order.objects.count(), 1)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BusinessCardTests(TestCase):
    def setUp(self):
        self.orga = make_user("orga", User.ORGANISATEUR, org_name="Orga Prod")
        self.spec = make_user("spec", User.SPECTATEUR)

    DATA = {"company_name": "Orga Prod", "tagline": "Événements", "contact_name": "Koffi A.",
            "job_title": "Directeur", "phone": "+229 97 00 11 22", "email": "c@orga.bj",
            "website": "www.orga.bj", "address": "Cotonou", "color": "#1d4e89"}

    def _create(self, user, **extra):
        self.client.force_login(user)
        return self.client.post(reverse("core:card_create"), {**self.DATA, **extra})

    def test_create_and_download_everything(self):
        r = self._create(self.orga, logo=png_file())
        card = BusinessCard.objects.get()
        self.assertRedirects(r, card.get_absolute_url())
        for side in ("recto", "verso"):
            resp = self.client.get(reverse("core:card_image", args=[card.pk, side]))
            self.assertEqual(resp["Content-Type"], "image/png")
            self.assertEqual(Image.open(BytesIO(resp.content)).size, (1050, 600))
        dl = self.client.get(reverse("core:card_image", args=[card.pk, "recto"]) + "?dl=1")
        self.assertIn("attachment", dl["Content-Disposition"])
        self.assertEqual(self.client.get(reverse("core:card_image", args=[card.pk, "dos"])).status_code, 404)
        pdf = self.client.get(reverse("core:card_pdf", args=[card.pk]))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(pdf.content.count(b"/Type /Page\n"), 2)   # recto + verso
        vcf = self.client.get(reverse("core:card_vcf", args=[card.pk])).content.decode()
        for needle in ("BEGIN:VCARD", "FN:Koffi A.", "ORG:Orga Prod", "TEL;TYPE=CELL:+229 97 00 11 22", "URL:https://www.orga.bj"):
            self.assertIn(needle, vcf)
        self.assertContains(self.client.get(reverse("core:card_list")), "Orga Prod")

    def test_spectateur_can_make_a_card_too(self):
        self._create(self.spec)
        self.assertEqual(BusinessCard.objects.filter(user=self.spec).count(), 1)

    def test_needs_a_phone_or_an_email(self):
        self._create(self.orga, phone="", email="")
        self.assertEqual(BusinessCard.objects.count(), 0)

    def test_cards_are_private(self):
        self._create(self.orga)
        card = BusinessCard.objects.get()
        self.client.force_login(self.spec)
        for name, args in (("card_detail", [card.pk]), ("card_pdf", [card.pk]), ("card_vcf", [card.pk]),
                           ("card_image", [card.pk, "recto"]), ("card_edit", [card.pk])):
            self.assertEqual(self.client.get(reverse(f"core:{name}", args=args)).status_code, 404, name)
        self.client.post(reverse("core:card_delete", args=[card.pk]))
        self.assertEqual(BusinessCard.objects.count(), 1)

    def test_edit_delete_and_prefill(self):
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("core:card_create")), 'value="Orga Prod"')
        self._create(self.orga)
        card = BusinessCard.objects.get()
        self.client.post(reverse("core:card_edit", args=[card.pk]), {**self.DATA, "company_name": "Nouveau Nom"})
        card.refresh_from_db()
        self.assertEqual(card.company_name, "Nouveau Nom")
        self.client.post(reverse("core:card_delete", args=[card.pk]))
        self.assertEqual(BusinessCard.objects.count(), 0)

    def test_very_long_texts_still_render(self):
        self._create(self.orga, company_name="X" * 74 + " " + "Y" * 5, tagline="T" * 100, address="A " * 70,
                     contact_name="N" * 80, job_title="J" * 80, website="w" * 120)
        card = BusinessCard.objects.get()
        for side in ("recto", "verso"):
            self.assertEqual(self.client.get(reverse("core:card_image", args=[card.pk, side])).status_code, 200)

    def test_buttons_are_visible_on_both_dashboards_and_nav(self):
        self.client.force_login(self.orga)
        self.assertContains(self.client.get(reverse("core:organizer_dashboard")), "Créer une carte de visite")
        self.client.force_login(self.spec)
        self.assertContains(self.client.get(reverse("core:spectateur_dashboard")), reverse("core:card_list"))
