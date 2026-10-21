from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.testutils import cleanup_media, image_file, media_override


@media_override
class RegistrationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cleanup_media()

    def payload(self, **over):
        data = dict(last_name="Dossou", first_name="Grâce", email="grace@example.com", country="BJ",
                    phone="01 97 12 34 56", sexe="F", profession="Étudiante", photo=image_file("p.png"),
                    password1="Sup3rSecret!x", password2="Sup3rSecret!x")
        data.update(over)
        return data

    def test_register_spectateur_stores_e164_phone(self):
        r = self.client.post(reverse("accounts:register", args=["spectateur"]), self.payload())
        self.assertRedirects(r, reverse("core:dashboard"), fetch_redirect_response=False)
        u = User.objects.get(email="grace@example.com")
        self.assertEqual((u.role, u.phone, u.country), ("spectateur", "+2290197123456", "BJ"))

    def test_phone_is_mandatory(self):
        r = self.client.post(reverse("accounts:register", args=["spectateur"]), self.payload(phone=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="grace@example.com").exists())

    def test_phone_must_match_country(self):
        r = self.client.post(reverse("accounts:register", args=["spectateur"]), self.payload(country="SN"))
        self.assertContains(r, "pays", status_code=200)
        self.assertFalse(User.objects.exists())

    def test_landline_rejected(self):
        r = self.client.post(reverse("accounts:register", args=["spectateur"]), self.payload(phone="+229 21 31 00 00"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_register_organisateur(self):
        p = self.payload(organisation_name="Ma Prod", photo="")
        del p["photo"]
        r = self.client.post(reverse("accounts:register", args=["organisateur"]), p)
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(email="grace@example.com")
        self.assertTrue(u.is_organisateur)
        self.assertEqual(u.organisation_name, "Ma Prod")

    def test_unknown_role_404(self):
        self.assertEqual(self.client.get("/compte/inscription/admin/").status_code, 404)

    def test_all_countries_listed_with_dial_codes(self):
        r = self.client.get(reverse("accounts:register", args=["spectateur"]))
        self.assertContains(r, "+229")
        self.assertGreater(len(r.context["countries"]), 200)
