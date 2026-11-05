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

    def test_footer_on_other_pages_for_visitor_not_for_spectator(self):
        self.assertContains(self.client.get(reverse("core:terms")), 'class="footer"')
        u = User.objects.create_user(email="s@x.test", username="spec1", password="pw123456!", role="spectateur")
        self.client.force_login(u)
        self.assertNotContains(self.client.get(reverse("core:terms")), 'class="footer"')

    def test_footer_hidden_for_organizer(self):
        u = User.objects.create_user(email="o@x.test", username="orga1", password="pw123456!", role="organisateur")
        self.client.force_login(u)
        self.assertNotContains(self.client.get("/"), 'class="footer"')

    def test_footer_hidden_on_home_even_for_visitor(self):
        self.client.logout()
        self.assertNotContains(self.client.get("/"), 'class="footer"')


class DeleteAccountTests(TestCase):
    def mk(self, role, n):
        return User.objects.create_user(email=f"d{n}@x.test", username=f"d{n}", password="pw123456!", role=role,
                                        first_name="Ada", last_name="Zinsou", phone="+22997000000")

    def test_profile_shows_delete_button_for_both_roles(self):
        for i, role in enumerate(("spectateur", "organisateur")):
            self.client.force_login(self.mk(role, i))
            self.assertContains(self.client.get(reverse("accounts:profile")), reverse("accounts:delete"))

    def test_wrong_password_or_word_keeps_account(self):
        u = self.mk("spectateur", 1)
        self.client.force_login(u)
        self.client.post(reverse("accounts:delete"), {"password": "nope", "confirm": "SUPPRIMER"})
        self.client.post(reverse("accounts:delete"), {"password": "pw123456!", "confirm": "oui"})
        u.refresh_from_db()
        self.assertTrue(u.is_active)

    def test_spectator_deleted_and_anonymised_keeps_orders(self):
        u = self.mk("spectateur", 2)
        self.client.force_login(u)
        r = self.client.post(reverse("accounts:delete"), {"password": "pw123456!", "confirm": "supprimer"})
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertEqual((u.phone, u.first_name), ("", "Compte"))
        self.assertTrue(u.email.endswith("@deleted.invalid"))
        self.assertFalse(u.has_usable_password())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(self.client.login(username="d2", password="pw123456!"))

    def test_organizer_with_balance_is_blocked(self):
        from unittest import mock
        u = self.mk("organisateur", 3)
        self.client.force_login(u)
        with mock.patch("accounts.services.organizer_balance", return_value=5000):
            self.client.post(reverse("accounts:delete"), {"password": "pw123456!", "confirm": "SUPPRIMER"})
            self.assertContains(self.client.get(reverse("accounts:delete")), "solde")
        u.refresh_from_db()
        self.assertTrue(u.is_active)

    def test_organizer_deleted_unpublishes_events(self):
        from accounts.services import delete_account
        u = self.mk("organisateur", 4)
        self.assertTrue(delete_account(u))
        u.refresh_from_db()
        self.assertFalse(u.is_active)

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse("accounts:delete")).status_code, 302)


class SignatureTests(TestCase):
    def setUp(self):
        import tempfile
        from django.test import override_settings
        self._tmp = tempfile.mkdtemp()
        self._ov = override_settings(MEDIA_ROOT=self._tmp)
        self._ov.enable()
        self.u = User.objects.create_user(email="sg@x.test", username="sg", password="pw123456!", role="organisateur",
                                          first_name="Ada", last_name="Zinsou", phone="+22997000000", sexe="F")
        self.client.force_login(self.u)

    def tearDown(self):
        import shutil
        self._ov.disable()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def post(self, **extra):
        data = {"last_name": "Zinsou", "first_name": "Ada", "sexe": "F", "country": "BJ", "phone": "97000000",
                "org_name": "Org", "signature_mode": "organizer", "signature": ""}
        data.update(extra)
        return self.client.post(reverse("accounts:profile"), data)

    def png_data_url(self):
        import base64, io
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
        ImageDraw.Draw(im).line([(10, 80), (150, 20), (290, 70)], fill=(18, 73, 127, 255), width=4)
        b = io.BytesIO(); im.save(b, "PNG")
        return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

    def test_profile_offers_three_signature_options(self):
        r = self.client.get(reverse("accounts:profile"))
        for t in ("Signature manuscrite", "Signature avec le nom de l", "Signature avec le nom du manager", "sig-canvas"):
            self.assertContains(r, t)

    def test_organizer_name_mode(self):
        self.post(signature_mode="organizer")
        self.u.refresh_from_db()
        self.assertEqual(self.u.signature_text, "Ada Zinsou")

    def test_manager_name_mode_requires_name(self):
        self.post(signature_mode="manager", signature="")
        self.u.refresh_from_db()
        self.assertNotEqual(self.u.signature_mode, "manager")
        self.post(signature_mode="manager", signature="Koffi Mensah – Directeur")
        self.u.refresh_from_db()
        self.assertEqual((self.u.signature_mode, self.u.signature_text), ("manager", "Koffi Mensah – Directeur"))

    def test_drawn_signature_saved_and_used_in_pdf_and_email(self):
        self.post(signature_mode="image", signature_drawn=self.png_data_url())
        self.u.refresh_from_db()
        self.assertEqual(self.u.signature_mode, "image")
        self.assertTrue(self.u.signature_png.startswith(b"\x89PNG"))
        from core.pdf import render_receipt
        from orders.services import build_receipt_email
        data = {"reference": "R1", "date": __import__("django.utils.timezone", fromlist=["now"]).now(), "thanks": "Merci", "event": None,
                "spectator": [("Email", "a@b.c")], "details_title": "D", "details": [("Objet", "x")], "status": "Payé", "total": 1000,
                "signature": self.u.signature_text, "signature_image": self.u.signature_png, "organizer": "Org", "qr": None}
        self.assertTrue(render_receipt(data).startswith(b"%PDF"))
        msg = build_receipt_email(data, to="a@b.c", subject="s")
        self.assertIn("cid:signature", msg.alternatives[0].content)
        self.assertIn("signature", [c for c, _ in msg.inline_images])

    def test_image_mode_without_image_is_rejected(self):
        self.post(signature_mode="image")
        self.u.refresh_from_db()
        self.assertNotEqual(self.u.signature_mode, "image")

    def test_garbage_image_rejected(self):
        self.post(signature_mode="image", signature_drawn="data:image/png;base64,AAAA")
        self.u.refresh_from_db()
        self.assertFalse(self.u.signature_image)

    def test_spectator_form_has_no_signature(self):
        s = User.objects.create_user(email="sp@x.test", username="sp", password="pw123456!", role="spectateur", phone="+22997000001")
        self.client.force_login(s)
        self.assertNotContains(self.client.get(reverse("accounts:profile")), "sig-canvas")
