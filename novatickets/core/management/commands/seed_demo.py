"""Données de démonstration réalistes : python manage.py seed_demo [--reset]"""
import io
import os
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts.models import User
from events.models import Event, TicketType
from orders.models import Order, Ticket, Withdrawal
from orders.services import create_order, pay_order, request_withdrawal

PASSWORD = "demo1234"
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def banner(title, subtitle, palette, size=(1200, 750)):
    w, h = size
    img = Image.new("RGB", size, palette[0])
    d = ImageDraw.Draw(img)
    for y in range(h):  # dégradé vertical
        t = y / h
        c = tuple(int(palette[0][i] * (1 - t) + palette[1][i] * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    for cx, cy, r, a in [(w * .82, h * .22, 230, 40), (w * .12, h * .85, 300, 30), (w * .6, h * .95, 180, 35)]:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(min(255, v + a) for v in palette[1]))
    d.text((60, h - 230), title, font=font(78), fill="white")
    d.text((60, h - 120), subtitle, font=font(38), fill=(220, 252, 231))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return ContentFile(buf.getvalue())


def badge(text, color, size=300):
    img = Image.new("RGB", (size, size), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, size - 10, size - 10), fill=color)
    d.text((size / 2, size / 2), text, font=font(120), fill="white", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Crée des organisateurs, spectateurs, événements, commandes et un retrait de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime d'abord les données de démo existantes.")

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(7)
        if opts["reset"]:
            emails = [u["email"] for u in ORGS + FANS]
            Withdrawal.objects.filter(organizer__email__in=emails).delete()
            Ticket.objects.filter(order__buyer__email__in=emails).delete()
            Order.objects.filter(buyer__email__in=emails).delete()
            Event.objects.filter(organizer__email__in=emails).delete()
            User.objects.filter(email__in=emails).delete()

        orgs = {}
        for spec in ORGS:
            u = self._user(spec, User.Role.ORGANISATEUR)
            if not u.org_logo:
                u.org_logo.save(f"{spec['key']}.png", badge(spec["org_name"][:1], spec["color"]), save=True)
            orgs[spec["key"]] = u
        fans = [self._user(spec, User.Role.SPECTATEUR) for spec in FANS]

        today = timezone.localdate()
        events = []
        for spec in EVENTS:
            if Event.objects.filter(name=spec["name"], organizer=orgs[spec["org"]]).exists():
                continue
            ev = Event(
                organizer=orgs[spec["org"]], name=spec["name"], description=spec["desc"], location=spec["location"],
                start_date=today + timedelta(days=spec["start"]), end_date=today + timedelta(days=spec["start"] + spec["length"]),
                start_time=spec["time"], purchase_deadline=today + timedelta(days=spec["start"] - 1 if spec["start"] > 0 else spec["start"] - 2),
                is_published=spec["published"],
            )
            ev.visual.save(f"{spec['org']}-{len(events)}.jpg", banner(spec["name"][:26], spec["location"], spec["palette"]), save=False)
            ev.logo.save(f"logo-{len(events)}.png", badge(spec["name"][:1], spec["palette"][0]), save=False)
            ev.save()
            for name, price, stock in spec["tickets"]:
                TicketType.objects.create(event=ev, name=name, price=price, stock=stock)
            events.append((ev, spec))

        # Commandes payées (créées à travers les services : commission calculée comme en production)
        for ev, spec in events:
            for fan in random.sample(fans, k=min(len(fans), spec["buyers"])):
                if not ev.is_published:
                    continue
                tt = random.choice(list(ev.ticket_types.all()))
                qty = random.choice([1, 1, 2, 3])
                order = create_order(fan, tt, qty) if not ev.sales_closed else self._backdated_order(fan, tt, qty)
                if order.status == Order.Status.PENDING:
                    pay_order(order, "card", "", send_email=False) if not ev.sales_closed else self._force_paid(order)
        # un organisateur qui achète chez un autre
        ev_other = next((e for e, s in events if s["org"] == "abidjan" and e.is_published and not e.sales_closed), None)
        if ev_other:
            tt = ev_other.ticket_types.first()
            o = create_order(orgs["cotonou"], tt, 1)
            pay_order(o, "mtn_bj", orgs["cotonou"].phone, send_email=False)

        # un retrait
        org = orgs["cotonou"]
        if not Withdrawal.objects.filter(organizer=org).exists():
            from orders.services import organizer_balance
            bal = organizer_balance(org)
            if bal >= 5000:
                request_withdrawal(org, (bal // 2 // 1000) * 1000, "mtn_bj", org.phone)

        self.stdout.write(self.style.SUCCESS("Données de démo prêtes."))
        self.stdout.write(f"Mot de passe de tous les comptes : {PASSWORD}")
        for s in ORGS + FANS:
            self.stdout.write(f"  {s['email']}")

    def _user(self, spec, role):
        u, created = User.objects.get_or_create(email=spec["email"], defaults={
            "username": spec["email"], "first_name": spec["first"], "last_name": spec["last"], "role": role,
            "country": spec["country"], "phone": spec["phone"], "sexe": spec["sexe"],
            "profession": spec.get("profession", ""), "org_name": spec.get("org_name", ""),
        })
        if created:
            u.set_password(PASSWORD)
            u.save()
        if not u.photo:
            u.photo.save(f"{spec['email'].split('@')[0]}.png", badge(u.initials, spec.get("color", (22, 163, 74))), save=True)
        return u

    def _backdated_order(self, fan, tt, qty):
        from orders.services import compute_amounts, make_reference
        total = tt.price * qty
        c, n = compute_amounts(total)
        return Order.objects.create(reference=make_reference("CMD"), buyer=fan, event=tt.event, ticket_type=tt, quantity=qty,
                                    unit_price=tt.price, total=total, commission=c, organizer_amount=n)

    def _force_paid(self, order):
        from orders.services import make_reference
        order.status = Order.Status.PAID
        order.paid_at = timezone.now() - timedelta(days=random.randint(15, 40))
        order.payment_method, order.payment_label = "mtn_bj", "MTN MoMo"
        order.save()
        for _ in range(order.quantity):
            Ticket.objects.create(order=order, reference=make_reference("TK", 10), used_at=order.paid_at + timedelta(days=12))


ORGS = [
    {"key": "cotonou", "email": "orga.cotonou@demo.test", "first": "Aïcha", "last": "Adjovi", "sexe": "F", "country": "BJ",
     "phone": "+2290197000001", "org_name": "Studio Cotonou Live", "color": (22, 163, 74)},
    {"key": "abidjan", "email": "orga.abidjan@demo.test", "first": "Yao", "last": "Kouassi", "sexe": "M", "country": "CI",
     "phone": "+2250707000002", "org_name": "Abidjan Events", "color": (21, 128, 61)},
]
FANS = [
    {"email": "fan.benin@demo.test", "first": "Koffi Marc", "last": "Dossou", "sexe": "M", "country": "BJ", "phone": "+2290197000003", "profession": "Étudiant", "color": (34, 197, 94)},
    {"email": "fan.ci@demo.test", "first": "Fatou", "last": "Traoré", "sexe": "F", "country": "CI", "phone": "+2250707000004", "profession": "Designer", "color": (22, 101, 52)},
    {"email": "fan.france@demo.test", "first": "Camille", "last": "Martin", "sexe": "F", "country": "FR", "phone": "+33612345605", "profession": "Ingénieure", "color": (20, 83, 45)},
    {"email": "fan.togo@demo.test", "first": "Kodjo", "last": "Agbeko", "sexe": "M", "country": "TG", "phone": "+22890000006", "profession": "Développeur", "color": (74, 222, 128)},
]
EVENTS = [
    {"org": "cotonou", "name": "Cotonou Jazz Nights", "desc": "Trois soirées de jazz et d'afro-fusion au bord de l'eau, avec des artistes de toute la sous-région.",
     "location": "Palais des Congrès, Cotonou", "start": 21, "length": 2, "time": "19:30", "published": True, "buyers": 3,
     "palette": [(21, 128, 61), (74, 222, 128)], "tickets": [("Standard", 5000, 300), ("VIP", 15000, 80), ("Table 6 pers.", 80000, 12)]},
    {"org": "cotonou", "name": "Tech Summit Bénin", "desc": "La conférence des développeurs, startups et créateurs de produits digitaux du Bénin.",
     "location": "Epitech Bénin, Cotonou", "start": 45, "length": 1, "time": "09:00", "published": True, "buyers": 4,
     "palette": [(22, 101, 52), (34, 197, 94)], "tickets": [("Étudiant", 2000, 150), ("Pass Standard", 10000, 200), ("Pass Pro", 25000, 50)]},
    {"org": "cotonou", "name": "Festival des Saveurs (brouillon)", "desc": "Festival gastronomique — en préparation.",
     "location": "Place de l'Amazone, Cotonou", "start": 90, "length": 2, "time": "11:00", "published": False, "buyers": 0,
     "palette": [(20, 83, 45), (134, 239, 172)], "tickets": [("Entrée", 1500, 1000)]},
    {"org": "abidjan", "name": "Nuit du Rire Abidjan", "desc": "Les meilleurs humoristes d'Afrique de l'Ouest réunis le temps d'une soirée.",
     "location": "Palais de la Culture, Abidjan", "start": 14, "length": 0, "time": "20:00", "published": True, "buyers": 4,
     "palette": [(21, 128, 61), (187, 247, 208)], "tickets": [("Classique", 7500, 400), ("Premium", 20000, 100)]},
    {"org": "abidjan", "name": "Afrobeat Open Air (complet)", "desc": "Un open air afrobeat — billets presque épuisés.",
     "location": "Parc des Expositions, Abidjan", "start": 30, "length": 0, "time": "17:00", "published": True, "buyers": 4,
     "palette": [(22, 163, 74), (21, 94, 55)], "tickets": [("Early bird", 4000, 6), ("Standard", 6000, 8)]},
    {"org": "cotonou", "name": "Concert Gospel de Septembre", "desc": "Soirée de louange — événement passé.",
     "location": "Stade de l'Amitié, Cotonou", "start": -24, "length": 0, "time": "18:00", "published": True, "buyers": 3,
     "palette": [(20, 83, 45), (74, 222, 128)], "tickets": [("Standard", 3000, 500)]},
]
