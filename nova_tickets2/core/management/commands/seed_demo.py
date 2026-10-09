"""Données de démonstration : python manage.py seed_demo"""
import io
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts.models import User
from core.models import BusinessCard
from events.models import Event, TicketType
from orders.models import Order, Withdrawal
from orders.services import confirm_payment

PASSWORD = "demo1234"


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_banner(text, c1, c2, size=(1200, 750)):
    w, h = size
    img = Image.new("RGB", size, c1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        col = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=col)
    d.ellipse((w - 420, -160, w + 120, 380), fill=(255, 255, 255, 40) if False else tuple(min(255, v + 25) for v in c2))
    d.text((60, h - 150), text, font=_font(72), fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue())


def make_avatar(letter, color):
    img = Image.new("RGB", (400, 500), color)
    d = ImageDraw.Draw(img)
    d.text((200, 250), letter, font=_font(220), fill="white", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue())


def make_logo(letter, color):
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 299, 299), 70, fill=color)
    d.text((150, 150), letter, font=_font(170), fill="white", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Crée des comptes, événements et ventes de démonstration."

    def handle(self, *args, **opts):
        if User.objects.filter(username="orga_benin").exists():
            self.stdout.write("Données de démo déjà présentes (supprimez db.sqlite3 pour repartir de zéro).")
            return

        # --- Organisateurs
        def organizer(username, first, last, org, country, phone, letter, color):
            u = User(username=username, first_name=first, last_name=last, email=f"{username}@demo.test",
                     role=User.ORGANISATEUR, country=country, phone=phone, org_name=org, sexe="M")
            u.set_password(PASSWORD)
            u.save()
            u.org_logo.save(f"{username}.png", make_logo(letter, color), save=True)
            return u

        o1 = organizer("orga_benin", "Koffi", "Ahouansou", "Afro Vibes Productions", "BJ", "+229 97 00 11 22", "A", (5, 150, 105, 255))
        o2 = organizer("orga_ci", "Awa", "Traoré", "Abidjan Live", "CI", "+225 07 00 11 22 33", "L", (234, 88, 12, 255))

        # --- Spectateurs
        def spectator(username, first, last, sexe, country, phone, color):
            u = User(username=username, first_name=first, last_name=last, email=f"{username}@demo.test",
                     role=User.SPECTATEUR, country=country, phone=phone, sexe=sexe, profession="Étudiant(e)")
            u.set_password(PASSWORD)
            u.save()
            u.photo.save(f"{username}.jpg", make_avatar(first[0], color), save=True)
            return u

        s1 = spectator("spec_marie", "Marie", "Dossou", "F", "BJ", "+229 96 11 22 33", (16, 185, 129))
        s2 = spectator("spec_jean", "Jean", "Kouassi", "M", "CI", "+225 05 11 22 33", (59, 130, 246))
        s3 = spectator("spec_fatou", "Fatou", "Diop", "F", "SN", "+221 77 123 45 67", (168, 85, 247))

        today = timezone.localdate()

        def event(org, name, desc, loc, delta, days, time, c1, c2, tickets, publish=True, logo=None):
            e = Event(organizer=org, name=name, description=desc, location=loc,
                      start_date=today + timedelta(days=delta), end_date=today + timedelta(days=delta + days),
                      start_time=time, sales_deadline=today + timedelta(days=delta + days),
                      status=Event.PUBLISHED if publish else Event.DRAFT)
            e.save()
            e.banner.save(f"{e.slug}.jpg", make_banner(name, c1, c2), save=True)
            for n, price, stock in tickets:
                TicketType.objects.create(event=e, name=n, price=price, stock=stock)
            return e

        import datetime as dt
        e1 = event(o1, "Cotonou Jazz Night", "Une soirée jazz en plein air avec les meilleurs artistes de la sous-région.",
                   "Palais des Congrès, Cotonou", 12, 0, dt.time(19, 0), (5, 150, 105), (6, 78, 59),
                   [("Standard", 5000, 300), ("VIP", 15000, 80), ("Table (4 pers.)", 50000, 20)])
        e2 = event(o1, "Festival Gospel Bénin", "Trois jours de louange, de concerts et de rencontres.",
                   "Stade de l'Amitié, Cotonou", 30, 2, dt.time(16, 30), (37, 99, 235), (30, 58, 138),
                   [("Pass journée", 3000, 500), ("Pass 3 jours", 7500, 200)])
        e3 = event(o2, "Abidjan Tech Summit", "La conférence des startups et du numérique en Afrique de l'Ouest.",
                   "Sofitel Ivoire, Abidjan", 20, 1, dt.time(9, 0), (234, 88, 12), (124, 45, 18),
                   [("Étudiant", 5000, 150), ("Professionnel", 25000, 200)])
        e4 = event(o2, "Dakar Beach Party", "Musique, plage et coucher de soleil.",
                   "Plage de Ngor, Dakar", 8, 0, dt.time(15, 0), (219, 39, 119), (131, 24, 67),
                   [("Entrée", 4000, 400), ("Pack boissons", 9000, 150)])
        event(o1, "Comédie Show (brouillon)", "Soirée stand-up, bientôt publiée.", "Cotonou", 45, 0, dt.time(20, 0),
              (202, 138, 4), (113, 63, 18), [("Standard", 4000, 200)], publish=False)

        # --- Ventes (organisateurs peuvent aussi acheter chez les autres)
        def buy(user, ev, ttype, qty, method):
            tt = ev.ticket_types.get(name=ttype)
            o = Order(user=user, event=ev, ticket_type=tt, quantity=qty)
            o.compute_amounts()
            o.save()
            confirm_payment(o, method, user.phone)

        buy(s1, e1, "VIP", 2, "MTN Mobile Money")
        buy(s1, e3, "Étudiant", 1, "Carte bancaire")
        buy(s2, e1, "Standard", 3, "Moov Money")
        buy(s2, e4, "Entrée", 2, "Wave")
        buy(s3, e1, "Table (4 pers.)", 1, "Carte bancaire")
        buy(s3, e2, "Pass journée", 2, "Carte bancaire")
        buy(o2, e1, "Standard", 1, "Wave")  # un organisateur achète chez un autre

        # --- Billets offerts à un ami (spectateur ET organisateur peuvent le faire)
        def gift(user, ev, ttype, qty, method, friend):
            tt = ev.ticket_types.get(name=ttype)
            o = Order(user=user, event=ev, ticket_type=tt, quantity=qty, for_friend=True,
                      friend_last_name=friend[0], friend_first_name=friend[1],
                      friend_sexe=friend[2], friend_email=friend[3])
            o.compute_amounts()
            o.save()
            confirm_payment(o, method, user.phone)

        gift(s1, e2, "Pass journée", 1, "MTN Mobile Money", ("Dossou", "Ruth", "F", "ruth@demo.test"))
        gift(o1, e3, "Étudiant", 1, "Moov Money", ("Houngbo", "Prince", "M", ""))

        # --- Carte de visite d'exemple pour l'organisateur béninois
        BusinessCard.objects.create(
            user=o1, company_name="Afro Vibes Productions", tagline="Concerts, festivals et événements d'entreprise",
            contact_name="Koffi Ahouansou", job_title="Directeur général", phone="+229 97 00 11 22",
            email="contact@afrovibes.demo", website="www.afrovibes.demo", address="Haie Vive, Cotonou, Bénin",
            color="#059669")

        # --- un retrait déjà traité
        Withdrawal.objects.create(organizer=o1, amount=20000, method="MTN Mobile Money", phone="+229 97 00 11 22", status="paid")

        self.stdout.write(self.style.SUCCESS(
            "Démo prête. Mot de passe de tous les comptes : %s\n"
            "  Organisateurs : orga_benin, orga_ci\n  Spectateurs   : spec_marie, spec_jean, spec_fatou" % PASSWORD))
