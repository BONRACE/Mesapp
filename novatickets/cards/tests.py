from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from cards.models import BusinessCard
from core.testutils import cleanup_media, image_file, make_user, media_override
from payments.models import Payment


@media_override
class BusinessCardTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cleanup_media()

    def setUp(self):
        self.user = make_user("c@t.nt")
        self.client.force_login(self.user)
        self.data = dict(theme="kraft", company_name="Atelier Test", contact_name="Awa Adjovi", job_title="Directrice",
                         phone="+229 01 97 12 34 56", email="awa@atelier.bj", website="www.atelier.bj",
                         address="Cotonou", tagline="Fait main")

    def create(self, **extra):
        r = self.client.post(reverse("cards:create"), {**self.data, **extra})
        return BusinessCard.objects.first(), r

    def test_create_then_pay_100_fcfa_then_download(self):
        card, r = self.create(logo=image_file("logo.png"))
        self.assertRedirects(r, card.get_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(card.is_paid)
        # aucune génération sans paiement validé
        for fmt in ("pdf", "recto", "verso"):
            r = self.client.get(reverse("cards:download", args=[card.pk, fmt]))
            self.assertRedirects(r, card.get_absolute_url(), fetch_redirect_response=False)
        # paiement via le même système que les tickets
        r = self.client.post(reverse("cards:pay", args=[card.pk]))
        payment = Payment.objects.get()
        self.assertEqual((payment.amount, payment.purpose), (settings.BUSINESS_CARD_PRICE, "card"))
        self.assertEqual(payment.amount, 100)
        self.assertRedirects(r, payment.get_checkout_url(), fetch_redirect_response=False)
        self.client.post(payment.get_checkout_url(), dict(method="mtn_momo", phone="+2290197123456"))
        card.refresh_from_db()
        self.assertTrue(card.is_paid)
        pdf = self.client.get(reverse("cards:download", args=[card.pk, "pdf"]))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        png = self.client.get(reverse("cards:download", args=[card.pk, "recto"]))
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertTrue(png.content.startswith(b"\x89PNG"))

    def test_failed_payment_keeps_card_locked(self):
        card, _ = self.create()
        self.client.post(reverse("cards:pay", args=[card.pk]))
        payment = Payment.objects.get()
        self.client.post(payment.get_checkout_url(), dict(method="mtn_momo", phone="+2290197123400"))
        card.refresh_from_db()
        self.assertFalse(card.is_paid)
        self.assertEqual(self.client.get(reverse("cards:download", args=[card.pk, "pdf"])).status_code, 302)

    def test_every_theme_renders_both_sides_and_live_preview(self):
        for theme, _label in BusinessCard.Theme.choices:
            for side in ("recto", "verso"):
                r = self.client.post(reverse("cards:live_preview"), {**self.data, "theme": theme, "side": side})
                self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"), (theme, side))
                self.assertEqual(self.client.get(reverse("cards:theme_sample", args=[theme, side])).status_code, 200)

    def test_cards_are_private(self):
        card, _ = self.create()
        self.client.force_login(make_user("other@t.nt", phone="+2290196123456"))
        self.assertEqual(self.client.get(card.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(reverse("cards:pay", args=[card.pk])).status_code, 404)

    def test_form_requires_company_and_contact(self):
        r = self.client.post(reverse("cards:create"), {**self.data, "company_name": ""})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(BusinessCard.objects.exists())
