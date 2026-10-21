"""Données de démonstration : `python manage.py seed_demo` (voir README pour les comptes).

Tout passe par les vrais services (commande → paiement simulé → signal → tickets → reçu),
ce qui valide au passage le parcours complet. Les e-mails de reçu ne sont pas affichés
dans le terminal pendant le seed (ajoutez --emails pour les envoyer vraiment).
"""
import io
import random
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts.models import User
from cards.models import BusinessCard
from events.models import Event, TicketType
from payments.models import Payment, Withdrawal
from payments.services import create_payment, process_payment, request_withdrawal
from tickets.models import Order, Ticket
from tickets.services import create_order

PASSWORD = "NovaTickets2026!"
ADMIN = ("admin@novatickets.bj", "Admin2026!")
FONTS = settings.BASE_DIR / "static" / "fonts"

ORGANISATEURS = [
    dict(email="orga.cotonou@demo.nt", last_name="ADJOVI", first_name="Mariam", country="BJ", phone="+2290197123456",
         sexe="F", profession="Productrice d'événements", organisation_name="Cotonou Live Productions", color=(21, 128, 61)),
    dict(email="orga.abidjan@demo.nt", last_name="KONÉ", first_name="Ibrahim", country="CI", phone="+2250707123456",
         sexe="M", profession="Directeur artistique", organisation_name="Lagune Events", color=(20, 40, 75)),
    dict(email="orga.dakar@demo.nt", last_name="DIOP", first_name="Awa", country="SN", phone="+221771234567",
         sexe="F", profession="Responsable culturelle", organisation_name="Teranga Culture", color=(180, 83, 9)),
]
SPECTATEURS = [
    dict(email="spectateur1@demo.nt", last_name="HOUNKPATIN", first_name="Eric", country="BJ", phone="+2290196123456", sexe="M", profession="Développeur"),
    dict(email="spectateur2@demo.nt", last_name="DOSSOU", first_name="Grâce", country="BJ", phone="+2290195234567", sexe="F", profession="Étudiante"),
    dict(email="spectateur3@demo.nt", last_name="AGBODJAN", first_name="Fabrice", country="BJ", phone="+2290161234567", sexe="M", profession="Entrepreneur"),
    dict(email="spectateur4@demo.nt", last_name="TRAORÉ", first_name="Fatou", country="CI", phone="+2250505123456", sexe="F", profession="Comptable"),
    dict(email="spectateur5@demo.nt", last_name="SOW", first_name="Moussa", country="SN", phone="+221761234567", sexe="M", profession="Photographe"),
]

# (organisateur index, nom, ville, lieu, décalage de jours, heure, types [(nom, prix, stock)], publié, description, couleur)
EVENTS = [
    (0, "Festival Jazz de Cotonou", "Cotonou", "Palais des Congrès", 21, "19:00",
     [("Standard", 5000, 300), ("VIP", 15000, 80), ("Gratuit étudiant", 0, 50)], True,
     "Trois soirées de jazz et d'afro-fusion avec des artistes du Bénin, du Nigéria et du Ghana.", (21, 128, 61)),
    (0, "Nuit de l'Entrepreneur Béninois", "Cotonou", "Hôtel du Lac", 35, "18:30",
     [("Pass simple", 10000, 150), ("Pass networking", 25000, 40)], True,
     "Conférences, ateliers et dîner de réseautage pour les entrepreneurs de la sous-région.", (14, 116, 144)),
    (0, "Tournoi de Maquis — Édition 2", "Porto-Novo", "Stade Charles de Gaulle", 60, "10:00",
     [("Entrée", 2000, 500)], False, "Brouillon : tournoi de football inter-quartiers.", (101, 163, 13)),
    (1, "Abidjan Afro Night", "Abidjan", "Palais de la Culture", 14, "20:00",
     [("Simple", 7500, 400), ("Carré Or", 30000, 60)], True,
     "La plus grande soirée afrobeats de la saison avec DJ sets et invités surprise.", (20, 40, 75)),
    (1, "Salon de la Tech Ouest-Africaine", "Abidjan", "Sofitel Ivoire", 45, "09:00",
     [("Visiteur", 3000, 600), ("Exposant", 50000, 30)], True,
     "Startups, investisseurs et développeurs réunis pendant deux jours.", (79, 70, 229)),
    (2, "Dakar Festival des Arts", "Dakar", "Place du Souvenir", 28, "17:00",
     [("Entrée", 4000, 350), ("Pass 3 jours", 9000, 120)], True,
     "Expositions, danse et musique live au bord de l'Atlantique.", (180, 83, 9)),
    (0, "Soirée Gospel — Louange Totale", "Cotonou", "Église Saint-Michel", -12, "17:00",
     [("Entrée libre", 0, 400), ("Soutien", 2000, 200)], True,
     "Soirée de louange et de chants (événement passé).", (126, 34, 206)),
    (1, "Marathon de la Lagune", "Abidjan", "Plateau", -30, "06:30",
     [("Inscription", 5000, 200)], True, "Course de 10 km le long de la lagune (événement passé).", (2, 132, 199)),
]


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _gradient(size, c1, c2):
    w, h = size
    img = Image.new("RGB", size, c1)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.6 + y / h * 0.4)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return img


def _png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ContentFile(buf.getvalue())


def event_visual(title, color):
    """Affiche : dégradé + formes + titre."""
    W, H = 1200, 750
    dark = tuple(int(c * 0.45) for c in color)
    img = _gradient((W, H), color, dark).convert("RGBA")
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.ellipse([W - 420, -160, W + 160, 420], fill=(255, 255, 255, 38))
    d.ellipse([-180, H - 360, 360, H + 180], fill=(255, 255, 255, 28))
    d.rectangle([70, 520, 250, 526], fill=(242, 140, 40, 255))
    img = Image.alpha_composite(img, over)
    d = ImageDraw.Draw(img)
    f = _font("Poppins-Bold.ttf", 78)
    words, lines, cur = title.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > W - 160 and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    y = 540
    for ln in lines[:3]:
        d.text((70, y), ln, font=f, fill="white")
        y += 92
    return _png(img.convert("RGB"))


def initials_image(text, color, circle=False):
    S = 400
    img = Image.new("RGB", (S, S), color)
    d = ImageDraw.Draw(img)
    f = _font("Poppins-Bold.ttf", 170)
    w = d.textlength(text, font=f)
    d.text(((S - w) / 2, 95), text, font=f, fill="white")
    return _png(img)


class Command(BaseCommand):
    help = "Crée des comptes, événements, commandes, tickets, retraits et cartes de visite de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime toutes les données avant de recréer la démo.")
        parser.add_argument("--emails", action="store_true", help="Envoie réellement les reçus (backend e-mail configuré).")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self.reset()
        elif User.objects.filter(email__endswith="@demo.nt").exists():
            raise CommandError("Les données de démo existent déjà. Relancez avec --reset pour repartir de zéro.")
        random.seed(42)
        ctx = override_settings() if opts["emails"] else override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
        with ctx, transaction.atomic():
            self.seed()
        self.report()

    # ------------------------------------------------------------------
    def reset(self):
        Payment.objects.all().delete()
        Withdrawal.objects.all().delete()
        Ticket.objects.all().delete()
        Order.objects.all().delete()
        Event.objects.all().delete()
        BusinessCard.objects.all().delete()
        User.objects.all().delete()
        self.stdout.write(self.style.WARNING("Base vidée."))

    def make_user(self, data, role):
        d = dict(data)
        color = d.pop("color", None) or random.choice([(21, 128, 61), (20, 40, 75), (180, 83, 9), (14, 116, 144), (126, 34, 206)])
        email = d.pop("email")
        user = User.objects.create_user(email, PASSWORD, role=role, **d)
        ini = (user.first_name[:1] + user.last_name[:1]).upper()
        user.photo.save(f"{user.pk}.png", initials_image(ini, color), save=False)
        if role == "organisateur":
            user.organisation_logo.save(f"org-{user.pk}.png", initials_image("".join(w[0] for w in user.organisation_name.split()[:2]).upper(), color), save=False)
        user.save()
        return user

    def seed(self):
        User.objects.create_superuser(ADMIN[0], ADMIN[1], first_name="Admin", last_name="NovaTickets", role="organisateur",
                                       country="BJ", phone="+2290197000001")
        orgs = [self.make_user(o, "organisateur") for o in ORGANISATEURS]
        specs = [self.make_user(s, "spectateur") for s in SPECTATEURS]

        events = []
        now = timezone.now()
        for oi, name, city, venue, days, hhmm, types, published, desc, color in EVENTS:
            start = timezone.localdate() + timedelta(days=max(days, 7))  # créé « à venir » pour pouvoir vendre
            hh, mm = map(int, hhmm.split(":"))
            ev = Event(organizer=orgs[oi], name=name, description=desc, venue=venue, city=city, start_date=start,
                       end_date=start + timedelta(days=2 if "Festival" in name or "Salon" in name else 0),
                       start_time=f"{hh:02d}:{mm:02d}", sales_deadline=now + timedelta(days=max(days, 7), hours=-2),
                       is_published=published)
            ev.visual.save(f"{name[:20]}.png", event_visual(name, color), save=False)
            if oi != 1 or "Marathon" not in name:
                ev.logo.save("logo.png", initials_image("".join(w[0] for w in name.split()[:2]).upper(), color), save=False)
            ev.save()
            for tname, price, stock in types:
                TicketType.objects.create(event=ev, name=tname, price=price, stock=stock)
            events.append((ev, days))

        # Commandes réalisées avec les vrais services (paiement simulé → signal → tickets → reçu).
        def buy(user, ev, type_index, qty, recipient=None, method=None):
            ttype = ev.ticket_types.all()[type_index]
            order, payment = create_order(user, ttype, qty, recipient)
            if not payment.is_succeeded:
                m = method or ("card" if user.country not in ("BJ", "CI", "SN") else
                               {"BJ": "mtn_momo", "CI": "orange_money", "SN": "wave"}[user.country])
                process_payment(payment, m, user.phone)
            return order

        jazz, entre, _tournoi, afro, tech, arts, gospel, marathon = [e for e, _ in events]
        for u in specs[:3]:
            buy(u, jazz, 0, random.randint(1, 3))
        buy(specs[0], jazz, 1, 1)
        buy(specs[1], jazz, 2, 1)
        buy(specs[1], entre, 0, 2)
        buy(specs[2], entre, 1, 1)
        buy(specs[3], afro, 0, 2)
        buy(specs[4], arts, 1, 1)
        buy(specs[0], afro, 1, 1)
        # Réservation pour un ami
        buy(specs[0], arts, 0, 1, recipient=dict(first_name="Koffi", last_name="AMOUSSOU", email="koffi.amoussou@demo.nt",
                                                  phone="+2290197555123", sexe="M", photo=None))
        buy(specs[3], tech, 0, 1, recipient=dict(first_name="Aminata", last_name="BAMBA", email="aminata.bamba@demo.nt",
                                                  phone="+2250707555123", sexe="F", photo=None))
        # Un organisateur achète chez un autre organisateur (autorisé) — mais pas chez lui-même
        buy(orgs[0], afro, 0, 1)
        buy(orgs[1], jazz, 0, 2)
        buy(orgs[2], tech, 0, 1)
        # Événements passés
        buy(specs[0], gospel, 0, 1)
        buy(specs[1], gospel, 1, 2)
        buy(specs[2], marathon, 0, 1)
        buy(specs[4], marathon, 0, 1)
        # Un ticket déjà utilisé
        used = Ticket.objects.filter(order__event=gospel).first()
        if used:
            used.used_at = now - timedelta(days=12)
            used.save(update_fields=["used_at"])

        # On recule les dates des événements « passés » (la vente a eu lieu avant).
        for ev, days in events:
            if days < 0:
                start = timezone.localdate() + timedelta(days=days)
                Event.objects.filter(pk=ev.pk).update(start_date=start, end_date=start,
                                                      sales_deadline=now + timedelta(days=days, hours=-2))

        # Retraits
        request_withdrawal(orgs[0], 8000, "mtn_momo", orgs[0].phone)
        request_withdrawal(orgs[0], 5000, "moov_money", "+2290196654321")
        request_withdrawal(orgs[1], 9000, "orange_money", orgs[1].phone)

        # Cartes de visite (2 payées, 1 en attente)
        cards = [
            dict(owner=specs[0], theme="emeraude", company_name="Atelier Cotonou", contact_name="Eric Hounkpatin",
                 job_title="Développeur web", phone="+229 01 96 12 34 56", email="eric@ateliercotonou.bj",
                 website="www.ateliercotonou.bj", address="Haie Vive, Cotonou", tagline="Le web qui vous ressemble"),
            dict(owner=specs[1], theme="kraft", company_name="Pagne & Co", contact_name="Grâce Dossou",
                 job_title="Créatrice", phone="+229 01 95 23 45 67", email="grace@pagne.co",
                 website="www.pagne.co", address="Marché Dantokpa, Cotonou", tagline="Tissé main, porté fièrement"),
            dict(owner=orgs[0], theme="minuit", company_name="Cotonou Live Productions", contact_name="Mariam Adjovi",
                 job_title="Directrice", phone="+229 01 97 12 34 56", email="contact@cotonoulive.bj",
                 website="www.cotonoulive.bj", address="Akpakpa, Cotonou", tagline="Vos événements, notre scène"),
        ]
        made = [BusinessCard.objects.create(**c) for c in cards]
        for card in made[:2]:
            p = create_payment(card.owner, "card", settings.BUSINESS_CARD_PRICE, card=card)
            process_payment(p, "mtn_momo", card.owner.phone)

    def report(self):
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
        self.stdout.write(f"  Utilisateurs : {User.objects.count()}  Événements : {Event.objects.count()}  "
                          f"Commandes : {Order.objects.filter(status='paid').count()}  Tickets : {Ticket.objects.count()}  "
                          f"Retraits : {Withdrawal.objects.count()}  Cartes : {BusinessCard.objects.count()}")
        self.stdout.write(f"  Mot de passe des comptes démo : {PASSWORD}   |   Admin : {ADMIN[0]} / {ADMIN[1]}")
