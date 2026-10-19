import re
from unittest import mock

from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import OTPCode, User

PHONE = "+2290196000001"


def login(client, phone=PHONE):
    """Parcours OTP complet ; renvoie (réponse verify, utilisateur)."""
    with mock.patch("accounts.views.send_sms") as sms:
        client.post("/api/auth/otp/request/", {"phone": phone}, format="json")
    code = re.search(r"\b(\d{6})\b", sms.call_args[0][1]).group(1)
    r = client.post("/api/auth/otp/verify/", {"phone": phone, "code": code}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return r, User.objects.get(pk=r.data["user"]["id"])  # le numéro saisi est normalisé côté serveur


class OTPTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_full_login_creates_user_and_returns_tokens(self):
        r, user = login(self.client, "+229 01 96 00 00 01")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_new"])
        self.assertEqual(user.phone, PHONE)  # normalisé en E.164
        self.assertFalse(user.profile_completed)

    def test_invalid_phone_rejected(self):
        r = self.client.post("/api/auth/otp/request/", {"phone": "123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_code_is_not_stored_in_clear_and_is_single_use(self):
        with mock.patch("accounts.views.send_sms") as sms:
            self.client.post("/api/auth/otp/request/", {"phone": PHONE}, format="json")
        code = re.search(r"\b(\d{6})\b", sms.call_args[0][1]).group(1)
        self.assertNotIn(code, OTPCode.objects.get().code_hash)
        ok = self.client.post("/api/auth/otp/verify/", {"phone": PHONE, "code": code}, format="json")
        again = self.client.post("/api/auth/otp/verify/", {"phone": PHONE, "code": code}, format="json")
        self.assertEqual((ok.status_code, again.status_code), (200, 400))

    def test_wrong_code_locks_after_max_attempts(self):
        with mock.patch("accounts.views.send_sms") as sms:
            self.client.post("/api/auth/otp/request/", {"phone": PHONE}, format="json")
        good = re.search(r"\b(\d{6})\b", sms.call_args[0][1]).group(1)
        bad = "000000" if good != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/otp/verify/", {"phone": PHONE, "code": bad}, format="json").status_code, 400)
        # même le bon code est refusé : le compteur d'essais a été persisté
        r = self.client.post("/api/auth/otp/verify/", {"phone": PHONE, "code": good}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_resend_cooldown(self):
        with mock.patch("accounts.views.send_sms"):
            self.client.post("/api/auth/otp/request/", {"phone": PHONE}, format="json")
            r = self.client.post("/api/auth/otp/request/", {"phone": PHONE}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertIn("retry_after", r.data)

    def test_onboarding_sets_role_once(self):
        _, user = login(self.client)
        r = self.client.patch("/api/me/", {"full_name": "Koffi D.", "role": "collector", "vehicle_type": "moto",
                                           "latitude": 6.36, "longitude": 2.39}, format="json")
        self.assertEqual(r.status_code, 200)
        user.refresh_from_db()
        self.assertEqual((user.role, user.profile_completed), ("collector", True))
        # le rôle ne peut plus être changé après l'inscription (pas d'auto-promotion)
        self.client.patch("/api/me/", {"role": "citizen"}, format="json")
        user.refresh_from_db()
        self.assertEqual(user.role, "collector")

    def test_cannot_self_assign_admin(self):
        login(self.client)
        r = self.client.patch("/api/me/", {"full_name": "Intrus", "role": "admin"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_endpoints_forbidden_for_citizen(self):
        login(self.client)
        self.assertEqual(self.client.get("/api/admin/stats/").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 403)
