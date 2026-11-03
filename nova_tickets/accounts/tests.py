from django.test import TestCase
from django.urls import reverse

from accounts.models import User

# Create your tests here.


class PasswordResetTests(TestCase):
    """Mot de passe oublié : e-mail, lien à usage unique, nouveau mot de passe, connexion."""

    def setUp(self):
        from accounts.models import User
        self.user = User.objects.create_user(username="m@t.test", email="m@t.test", password="ancien-mdp-123", role="spectateur",
                                             first_name="Mina", last_name="Test", phone="+22997000000")

    def _link(self):
        import re
        from django.core import mail
        body = mail.outbox[-1].body
        return re.search(r"https?://[^/]+(/\S+)", body).group(1)

    def test_full_flow(self):
        from django.core import mail
        r = self.client.post(reverse("accounts:password_reset"), {"email": "m@t.test"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["m@t.test"])
        self.assertIn("<a href=", mail.outbox[0].alternatives[0][0])
        link = self._link()
        r = self.client.get(link, follow=True)                       # Django redirige vers une URL sans jeton (session)
        self.assertContains(r, "Nouveau mot de passe")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "Nouveau-mdp-9876", "new_password2": "Nouveau-mdp-9876"})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.assertTrue(self.client.login(username="m@t.test", password="Nouveau-mdp-9876"))
        self.client.logout()
        self.assertFalse(self.client.login(username="m@t.test", password="ancien-mdp-123"))
        self.assertContains(self.client.get(link, follow=True), "Lien invalide ou expiré")   # usage unique

    def test_unknown_email_gives_same_answer_and_no_mail(self):
        from django.core import mail
        r = self.client.post(reverse("accounts:password_reset"), {"email": "inconnu@t.test"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))   # on ne révèle pas si le compte existe
        self.assertEqual(len(mail.outbox), 0)

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))


class RegistrationAndLoginTests(TestCase):
    """Inscription (maquette) : nom d'utilisateur, onglets, pays/téléphone ; connexion par e-mail OU identifiant."""

    def _photo(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (40, 40), (22, 163, 74)).save(buf, "PNG")
        return SimpleUploadedFile("p.png", buf.getvalue(), content_type="image/png")

    def data(self, **extra):
        d = {"last_name": "Dossou", "first_name": "Marc", "sexe": "M", "profession": "", "email": "marc@t.test", "username": "marc_d",
             "country": "BJ", "phone": "97 00 00 11", "password1": "Sup3r-Secret-99", "password2": "Sup3r-Secret-99", "photo": self._photo()}
        d.update(extra)
        return d

    def test_page_follows_mockup(self):
        html = self.client.get(reverse("accounts:register_spectateur")).content.decode()
        for text in ("Spectateur", "Organisateur", "Créer un compte spectateur", "Nom d&#x27;utilisateur", "Téléphone mobile", "+229",
                     "Elle apparaîtra sur votre billet.", "Créer mon compte", "Conditions Générales d"):
            self.assertIn(text, html)
        self.assertIn("🇧🇯 Bénin (+229)", html)                      # liste de pays avec drapeau et indicatif
        self.assertContains(self.client.get(reverse("accounts:register_organisateur")), "Créer un compte organisateur")
        self.assertRedirects(self.client.get(reverse("accounts:register")), reverse("accounts:register_spectateur"))

    def test_register_with_username_then_login_both_ways(self):
        r = self.client.post(reverse("accounts:register_spectateur"), self.data())
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(email="marc@t.test")
        self.assertEqual((user.username, user.phone), ("marc_d", "+22997000011"))
        self.client.logout()
        for ident in ("marc@t.test", "MARC@t.test", "marc_d", "Marc_D"):
            self.assertTrue(self.client.login(username=ident, password="Sup3r-Secret-99"), ident)
            self.client.logout()
        self.assertFalse(self.client.login(username="marc_d", password="mauvais"))
        r = self.client.post(reverse("accounts:login"), {"username": "marc_d", "password": "Sup3r-Secret-99"})
        self.assertEqual(r.status_code, 302)

    def test_username_must_be_unique_and_valid(self):
        self.client.post(reverse("accounts:register_spectateur"), self.data())
        self.client.logout()
        r = self.client.post(reverse("accounts:register_spectateur"), self.data(email="autre@t.test", username="MARC_D"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="autre@t.test").exists())
        r = self.client.post(reverse("accounts:register_spectateur"), self.data(email="autre@t.test", username="marc@t.test"))
        self.assertEqual(r.status_code, 200)                             # un identifiant ne peut pas être l'e-mail d'un autre compte
        r = self.client.post(reverse("accounts:register_spectateur"), self.data(email="autre@t.test", username="nom invalide !"))
        self.assertEqual(r.status_code, 200)

    def test_profession_optional_photo_required(self):
        r = self.client.post(reverse("accounts:register_spectateur"), self.data(photo=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="marc@t.test").exists())

    def test_organizer_registration(self):
        d = {"org_name": "Studio Nova", "last_name": "Adjovi", "first_name": "Aïcha", "sexe": "F", "email": "orga@t.test", "username": "studio_nova",
             "country": "CI", "phone": "07 07 00 00 12", "password1": "Sup3r-Secret-99", "password2": "Sup3r-Secret-99"}
        self.assertEqual(self.client.post(reverse("accounts:register_organisateur"), d).status_code, 302)
        u = User.objects.get(email="orga@t.test")
        self.assertEqual((u.role, u.username, u.phone[:4]), ("organisateur", "studio_nova", "+225"))


class FooterVisibilityTests(TestCase):
    def test_footer_hidden_on_login_and_reset(self):
        for name in ("accounts:login", "accounts:password_reset"):
            self.assertNotContains(self.client.get(reverse(name)), 'class="footer"')

    def test_footer_on_home_for_visitor_not_for_spectator(self):
        self.assertContains(self.client.get("/"), 'class="footer"')
        u = User.objects.create_user(email="s@x.test", username="spec1", password="pw123456!", role="spectateur")
        self.client.force_login(u)
        self.assertNotContains(self.client.get("/"), 'class="footer"')

    def test_footer_hidden_for_organizer(self):
        u = User.objects.create_user(email="o@x.test", username="orga1", password="pw123456!", role="organisateur")
        self.client.force_login(u)
        self.assertNotContains(self.client.get("/"), 'class="footer"')
