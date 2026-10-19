"""Vérifie la configuration e-mail du fichier .env :  python manage.py send_test_email vous@gmail.com"""
import smtplib
import socket

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envoie un e-mail de test pour vérifier la configuration d'envoi (section E-mails du .env)."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Adresse qui doit recevoir l'e-mail de test")

    def handle(self, *args, **opts):
        s = settings
        self.stdout.write(f"Backend : {s.EMAIL_BACKEND}")
        if s.EMAIL_BACKEND.endswith("console.EmailBackend"):
            self.stdout.write(self.style.WARNING(
                "\nEMAIL_BACKEND=console : l'e-mail va seulement s'AFFICHER ci-dessous, il ne sera PAS envoyé.\n"
                "Pour de vrais e-mails, passez à django.core.mail.backends.smtp.EmailBackend dans .env.\n"))
        else:
            self.stdout.write(f"Serveur : {s.EMAIL_HOST}:{s.EMAIL_PORT}  TLS={s.EMAIL_USE_TLS}  SSL={s.EMAIL_USE_SSL}")
            self.stdout.write(f"Compte  : {s.EMAIL_HOST_USER or '(aucun)'}   Expéditeur : {s.DEFAULT_FROM_EMAIL}\n")
        try:
            send_mail("Test NovaTickets", "Si vous lisez ceci, l'envoi d'e-mails fonctionne ✔",
                      s.DEFAULT_FROM_EMAIL, [opts["to"]], fail_silently=False)
        except smtplib.SMTPAuthenticationError:
            self._fail("Identifiants refusés par le serveur.",
                       "Gmail : activez la validation en 2 étapes puis créez un « mot de passe d'application » "
                       "(16 caractères) à mettre dans EMAIL_HOST_PASSWORD. Le mot de passe habituel est refusé.")
        except smtplib.SMTPSenderRefused:
            self._fail("Adresse expéditeur refusée.",
                       "DEFAULT_FROM_EMAIL doit utiliser la même adresse que EMAIL_HOST_USER.")
        except smtplib.SMTPRecipientsRefused:
            self._fail("Adresse destinataire refusée.", "Vérifiez l'adresse saisie.")
        except socket.gaierror:
            self._fail("Serveur introuvable.", "Vérifiez EMAIL_HOST (Gmail : smtp.gmail.com) et votre connexion Internet.")
        except (TimeoutError, ConnectionRefusedError, smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError):
            self._fail("Connexion impossible au serveur.",
                       "Port 587 → EMAIL_USE_TLS=True / EMAIL_USE_SSL=False ; port 465 → EMAIL_USE_SSL=True / EMAIL_USE_TLS=False. "
                       "Un pare-feu ou un réseau d'entreprise peut aussi bloquer ces ports.")
        except Exception as exc:  # noqa: BLE001
            self._fail(f"{type(exc).__name__} : {exc}", "Vérifiez la section E-mails du fichier .env.")
        else:
            self.stdout.write(self.style.SUCCESS(f"✔ E-mail de test envoyé à {opts['to']} (pensez à regarder les spams)."))

    def _fail(self, problem, hint):
        self.stderr.write(self.style.ERROR(f"✘ {problem}"))
        self.stderr.write(f"  → {hint}")
