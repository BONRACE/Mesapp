from django.test import SimpleTestCase

from config.mailconf import clean_password, default_sender, pick_backend

SMTP = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE = "django.core.mail.backends.console.EmailBackend"


class MailConfTests(SimpleTestCase):
    def test_credentials_select_smtp_automatically(self):
        self.assertEqual(pick_backend("", "me@gmail.com", "secret", False), SMTP)

    def test_no_credentials_falls_back_to_console(self):
        self.assertEqual(pick_backend("", "", "", False), CONSOLE)

    def test_force_console_wins_over_credentials(self):
        self.assertEqual(pick_backend("", "me@gmail.com", "secret", True), CONSOLE)

    def test_explicit_real_backend_is_respected(self):
        self.assertEqual(pick_backend(SMTP, "", "", False), SMTP)

    def test_explicit_console_with_credentials_still_sends(self):
        self.assertEqual(pick_backend(CONSOLE, "me@gmail.com", "secret", False), SMTP)

    def test_gmail_app_password_spaces_removed(self):
        self.assertEqual(clean_password("abcd efgh ijkl mnop", "smtp.gmail.com"), "abcdefghijklmnop")
        self.assertEqual(clean_password("a b", "mail.example.com"), "a b")

    def test_default_sender(self):
        self.assertIn("me@gmail.com", default_sender("", "NovaTickets", "me@gmail.com"))
