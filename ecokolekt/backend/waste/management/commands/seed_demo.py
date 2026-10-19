"""Données de départ.

  python manage.py seed_demo --reference-only   # catégories + points d'apport (sûr en production)
  python manage.py seed_demo                    # + comptes, annonces et demandes de démonstration (dev uniquement)

Comptes de démo (OTP affiché dans la console du serveur / champ dev_code) :
  admin +229 01 97 00 00 01 · citoyens +229 01 96 00 00 01, +229 01 61 23 45 67
  collecteurs +229 01 97 12 34 56, +229 01 55 12 34 56 · recycleur +229 01 66 12 34 56
"""
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from accounts.models import CollectorProfile, RecyclerProfile, User
from marketplace.models import Listing
from waste.models import CollectionPoint, PickupRequest, WasteCategory
from waste.services import assign_nearest_collector

CATEGORIES = [
    ("plastique", "Plastique (PET, PEHD)", "#E8B100", 12, True),
    ("papier", "Papier & carton", "#2D6CDF", 8, True),
    ("metal", "Métaux", "#6B7280", 15, True),
    ("verre", "Verre", "#2E9E5B", 6, True),
    ("organique", "Organique / compost", "#8A5A2B", 4, True),
    ("deee", "Électronique (DEEE)", "#7C4DFF", 18, True),
    ("autres", "Autres déchets", "#9AA39C", 2, False),
]

# (nom, type, lat, lng, adresse, codes catégories)
POINTS = [
    ("Centre de tri Dantokpa", "center", 6.3665, 2.4350, "Marché Dantokpa", ["plastique", "papier", "metal", "verre"]),
    ("Point d'apport Cadjèhoun", "dropoff", 6.3600, 2.3850, "Cadjèhoun, près du carrefour", ["plastique", "papier", "verre"]),
    ("Point d'apport Fidjrossè", "dropoff", 6.3560, 2.3550, "Fidjrossè plage", ["plastique", "verre"]),
    ("Point d'apport Akpakpa", "dropoff", 6.3560, 2.4400, "Akpakpa, route des pêches", ["plastique", "papier", "metal"]),
    ("Bac de quartier Haie Vive", "bin", 6.3620, 2.3990, "Haie Vive", ["plastique", "papier"]),
    ("Centre DEEE Ganhi", "center", 6.3640, 2.4250, "Ganhi", ["deee", "metal"]),
]

USERS = [
    ("+2290197000001", "Administration EcoKolekt", User.Role.ADMIN, None),
    ("+2290196000001", "Aminata Houngbo", User.Role.CITIZEN, (6.3610, 2.3880)),
    ("+2290161234567", "Rodrigue Adjovi", User.Role.CITIZEN, (6.3590, 2.4120)),
    ("+2290197123456", "Koffi Dossou", User.Role.COLLECTOR, (6.3630, 2.3950)),
    ("+2290155123456", "Séraphin Gbédjinou", User.Role.COLLECTOR, (6.3570, 2.4300)),
    ("+2290166123456", "Plastic Bénin SARL", User.Role.RECYCLER, (6.3650, 2.4200)),
]

# (catégorie, titre, kg, FCFA/kg, min kg, grade, vendeur index dans USERS)
LISTINGS = [
    ("plastique", "Bouteilles PET transparentes, triées", 850, 140, 50, "clean", 3),
    ("plastique", "PEHD colorés (bidons, seaux)", 400, 110, 30, "sorted", 4),
    ("papier", "Carton ondulé pressé en balles", 1200, 65, 100, "baled", 4),
    ("metal", "Canettes aluminium compactées", 260, 520, 20, "sorted", 3),
    ("metal", "Ferraille mixte", 3000, 130, 200, "raw", 4),
    ("verre", "Bouteilles en verre, sans bouchons", 700, 25, 100, "sorted", 3),
    ("organique", "Compost mûr (sacs de 25 kg)", 500, 60, 25, "clean", 5),
]

DEMO_PICKUPS = [
    ("plastique", "Cadjèhoun, rue 214", 6.3612, 2.3871, 8),
    ("papier", "Haie Vive, face pharmacie", 6.3598, 2.4015, 12),
    ("verre", "Zogbo, carrefour", 6.3705, 2.3980, 6),
    ("metal", "Akpakpa, Missessin", 6.3550, 2.4310, 20),
]


class Command(BaseCommand):
    help = "Crée les catégories, points d'apport et (sans --reference-only) des données de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--reference-only", action="store_true")
        parser.add_argument("--force", action="store_true", help="Autorise les données de démo avec DEBUG=False.")

    def handle(self, *args, **opts):
        cats = self._categories()
        self._points(cats)
        if opts["reference_only"]:
            return self.stdout.write(self.style.SUCCESS("Données de référence prêtes."))
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Refus : comptes de démo avec DEBUG=False. Utilisez --reference-only (ou --force).")
        users = self._users()
        self._listings(cats, users)
        self._pickups(cats, users)
        self.stdout.write(self.style.SUCCESS("Données de démonstration prêtes."))

    def _categories(self):
        out = {}
        for code, name, color, pts, rec in CATEGORIES:
            out[code], _ = WasteCategory.objects.update_or_create(
                code=code, defaults={"name": name, "color": color, "points_per_kg": pts, "is_recyclable": rec}
            )
        return out

    def _points(self, cats):
        for name, kind, lat, lng, addr, codes in POINTS:
            p, _ = CollectionPoint.objects.get_or_create(
                name=name, defaults={"kind": kind, "location": Point(lng, lat, srid=4326), "address": addr}
            )
            p.categories.set([cats[c] for c in codes])

    def _users(self):
        users = []
        for phone, name, role, pos in USERS:
            u, _ = User.objects.get_or_create(phone=phone)
            u.full_name, u.role, u.is_approved, u.profile_completed = name, role, True, True
            u.is_staff = u.is_superuser = role == User.Role.ADMIN
            if pos:
                u.location = Point(pos[1], pos[0], srid=4326)
            u.save()
            if role == User.Role.COLLECTOR:
                CollectorProfile.objects.update_or_create(
                    user=u, defaults={"vehicle_type": "truck" if "Séraphin" in name else "moto", "is_on_duty": True,
                                      "current_location": u.location, "last_seen": timezone.now(),
                                      "capacity_kg": 1500 if "Séraphin" in name else 250},
                )
            if role == User.Role.RECYCLER:
                RecyclerProfile.objects.update_or_create(user=u, defaults={"company_name": name, "address": "Zone industrielle, Cotonou"})
            users.append(u)
        return users

    def _listings(self, cats, users):
        for code, title, kg, price, minkg, grade, idx in LISTINGS:
            seller = users[idx]
            Listing.objects.get_or_create(
                seller=seller, title=title,
                defaults={"category": cats[code], "quantity_kg": Decimal(kg), "unit_price": price, "min_order_kg": Decimal(minkg),
                          "grade": grade, "location": seller.location, "address": "Cotonou"},
            )

    def _pickups(self, cats, users):
        citizens = [u for u in users if u.role == User.Role.CITIZEN]
        if PickupRequest.objects.exists():
            return
        for i, (code, addr, lat, lng, kg) in enumerate(DEMO_PICKUPS):
            p = PickupRequest.objects.create(
                citizen=citizens[i % len(citizens)], category=cats[code], address=addr,
                location=Point(lng, lat, srid=4326), estimated_weight_kg=Decimal(kg),
            )
            assign_nearest_collector(p)
