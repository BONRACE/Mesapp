"""Test de fumée : toutes les pages se rendent, pour chaque type d'utilisateur."""
from django.test import TestCase
from django.urls import reverse

from cards.models import BusinessCard
from core.testutils import cleanup_media, make_event, make_user, media_override
from payments.models import Payment
from payments.services import create_payment, process_payment
from tickets.models import Ticket
from tickets.services import create_order


@media_override
class SmokeTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cleanup_media()

    @classmethod
    def setUpTestData(cls):
        cls.orga = make_user("o@t.nt", "organisateur")
        cls.spec = make_user("s@t.nt", phone="+2290196123456")
        cls.event = make_event(cls.orga)
        cls.order, cls.payment = create_order(cls.spec, cls.event.ticket_types.get(), 1)
        process_payment(cls.payment, "mtn_momo", cls.spec.phone)
        cls.ticket = Ticket.objects.get()
        cls.card = BusinessCard.objects.create(owner=cls.spec, company_name="X", contact_name="Y")

    def ok(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r

    def test_public_pages(self):
        for url in ["/", reverse("events:list"), self.event.get_absolute_url(), reverse("accounts:login"),
                    reverse("accounts:register_choice"), reverse("accounts:register", args=["spectateur"]),
                    reverse("accounts:register", args=["organisateur"]), reverse("tickets:verify", args=[self.ticket.token])]:
            self.ok(url)
        self.assertEqual(self.client.get("/nimporte/quoi/").status_code, 404)

    def test_spectator_pages(self):
        self.client.force_login(self.spec)
        for url in [reverse("tickets:dashboard"), self.ticket.get_absolute_url(), reverse("tickets:order_detail", args=[self.order.reference]),
                    reverse("accounts:profile"), reverse("payments:history"), reverse("cards:list"), reverse("cards:create"),
                    reverse("cards:detail", args=[self.card.pk]), reverse("cards:edit", args=[self.card.pk]),
                    reverse("tickets:buy", args=[self.event.slug]), self.event.get_absolute_url()]:
            self.ok(url)
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("tickets:dashboard"))

    def test_organizer_pages(self):
        self.client.force_login(self.orga)
        for url in [reverse("events:dashboard"), reverse("events:create"), reverse("events:edit", args=[self.event.slug]),
                    reverse("events:manage", args=[self.event.slug]), reverse("payments:withdrawals"), reverse("tickets:dashboard"),
                    reverse("tickets:verify", args=[self.ticket.token]), self.event.get_absolute_url()]:
            self.ok(url)
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("events:dashboard"))
        r = self.ok(reverse("tickets:verify", args=[self.ticket.token]))
        self.assertContains(r, "Valider l'entrée")

    def test_checkout_page(self):
        pay = create_payment(self.spec, "card", 100, card=self.card)
        self.client.force_login(self.spec)
        r = self.ok(pay.get_checkout_url())
        self.assertContains(r, "MTN MoMo")
        self.assertContains(r, "Carte bancaire")
        # le paiement d'un autre utilisateur est introuvable
        self.client.force_login(self.orga)
        self.assertEqual(self.client.get(pay.get_checkout_url()).status_code, 404)
