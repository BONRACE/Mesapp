"""Remplit la base avec des données de démonstration réalistes.

Usage : python manage.py seed_demo          (idempotent : relancer ne duplique rien)
        python manage.py seed_demo --reset  (efface les données de démo avant)
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ProfilOrganisateur, Role, User
from apps.cards.models import CarteVisite
from apps.events.models import Evenement, TypeTicket
from apps.payments.models import Paiement, Retrait
from apps.payments.services import PanierItem, creer_commande, lancer_paiement
from apps.tickets.models import Commande, Ticket

MOT_DE_PASSE = "demo12345"

ORGANISATEURS = [
    dict(email="orga.vibes@novatickets.demo", prenom="Serge", nom="Adjovi", pays="BJ", tel="97123456",
         structure="Vibes Events Bénin", description="Festivals et concerts à Cotonou.", site="https://vibes.example.bj", verifie=True),
    dict(email="orga.lagune@novatickets.demo", prenom="Awa", nom="Koné", pays="CI", tel="0707123456",
         structure="Lagune Productions", description="Salons professionnels et conférences à Abidjan.", site="", verifie=True),
    dict(email="orga.sahel@novatickets.demo", prenom="Ibrahim", nom="Ouédraogo", pays="BF", tel="70123456",
         structure="Sahel Culture", description="Théâtre et cinéma à Ouagadougou.", site="", verifie=False),
]

SPECTATEURS = [
    dict(email="aicha.mensah@novatickets.demo", prenom="Aïcha", nom="Mensah", sexe="F", profession="Juriste", pays="BJ", tel="97556677"),
    dict(email="koffi.hounkpe@novatickets.demo", prenom="Koffi", nom="Hounkpè", sexe="H", profession="Ingénieur logiciel", pays="BJ", tel="66112233"),
    dict(email="fatou.diallo@novatickets.demo", prenom="Fatou", nom="Diallo", sexe="F", profession="Médecin", pays="SN", tel="771234567"),
    dict(email="yao.kouame@novatickets.demo", prenom="Yao", nom="Kouamé", sexe="H", profession="Comptable", pays="CI", tel="0501020304"),
    dict(email="mariam.traore@novatickets.demo", prenom="Mariam", nom="Traoré", sexe="F", profession="Architecte", pays="ML", tel="76001122"),
]

# Événements : (organisateur, nom, ville, lieu, jours_depuis_aujourd_hui_debut, duree_jours, heure, types, statut)
EVENEMENTS = [
    ("orga.vibes", "Festival Vibes Cotonou 2026", "Cotonou", "Stade de l'Amitié", 24, 2, time(18, 0),
     [("Pass Général", 5000, 800), ("VIP Gold", 25000, 120), ("Table 8 personnes", 150000, 10)], "publie"),
    ("orga.vibes", "Soirée Afrobeats & Jazz", "Porto-Novo", "Esplanade Gbessou", 9, 1, time(20, 30),
     [("Entrée simple", 3000, 300), ("Carré VIP", 15000, 40)], "publie"),
    ("orga.lagune", "Salon de l'Entrepreneuriat Lagune", "Abidjan", "Palais des Congrès", 40, 3, time(9, 0),
     [("Visiteur", 10000, 1500), ("Exposant pass", 60000, 80)], "publie"),
    ("orga.lagune", "Conférence Tech Afrique de l'Ouest", "Abidjan", "Hôtel Ivoire", 15, 1, time(8, 30),
     [("Standard", 20000, 250), ("Early bird", 12000, 50)], "publie"),
    ("orga.sahel", "Festival du Film Sahel", "Ouagadougou", "Ciné Sahel", 60, 4, time(19, 0),
     [("Séance unique", 2000, 200), ("Pass 4 jours", 12000, 60)], "publie"),
    ("orga.vibes", "Gala caritatif (brouillon)", "Cotonou", "Hôtel Novotel", 80, 1, time(20, 0),
     [("Table", 100000, 20)], "brouillon"),
]

CARTES = [
    ("aicha.mensah", "Mensah & Associés", "Aïcha Mensah", "Juriste d'affaires", "+229 97 55 66 77", "aicha.mensah@novatickets.demo", "mensah-avocats.bj", "Cotonou, Haie Vive", "Le droit, en clair.", "emeraude"),
    ("koffi.hounkpe", "Hounkpè Digital", "Koffi Hounkpè", "Ingénieur logiciel", "+229 66 11 22 33", "koffi@hounkpe.dev", "hounkpe.dev", "Porto-Novo", "Du code qui tient debout.", "minimal"),
]


def _email_vers_user(prefixe):
    return User.objects.filter(email__startswith=prefixe + "@").first()


class Command(BaseCommand):
    help = "Crée des comptes, événements, commandes, tickets, retraits et cartes de visite de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime d'abord les données de démo.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(2026)
        if options["reset"]:
            self._reset()

        self.stdout.write(self.style.MIGRATE_HEADING("Création des organisateurs"))
        orgas = {}
        for o in ORGANISATEURS:
            user = self._user(o["email"], Role.ORGANISATEUR, o["prenom"], o["nom"], o["pays"], o["tel"], profession="Organisateur")
            ProfilOrganisateur.objects.update_or_create(
                utilisateur=user,
                defaults=dict(structure=o["structure"], description=o["description"], site_web=o["site"], verifie=o["verifie"]),
            )
            orgas[o["email"].split("@")[0]] = user

        self.stdout.write(self.style.MIGRATE_HEADING("Création des spectateurs"))
        specs = []
        for s in SPECTATEURS:
            specs.append(self._user(s["email"], Role.SPECTATEUR, s["prenom"], s["nom"], s["pays"], s["tel"], sexe=s["sexe"], profession=s["profession"]))

        self.stdout.write(self.style.MIGRATE_HEADING("Création des événements et types de tickets"))
        evenements = []
        aujourdhui = timezone.localdate()
        for org_key, nom, ville, lieu, debut_j, duree, heure, types, statut in EVENEMENTS:
            debut = aujourdhui + timedelta(days=debut_j)
            fin = debut + timedelta(days=duree - 1)
            limite = timezone.make_aware(datetime.combine(debut - timedelta(days=1), time(23, 59)))
            ev, _ = Evenement.objects.update_or_create(
                nom=nom,
                defaults=dict(
                    organisateur=orgas[org_key], description=f"{nom} à {ville}. Billets nominatifs, entrée contrôlée par QR code.",
                    lieu=lieu, ville=ville, date_debut=debut, date_fin=fin, heure_debut=heure,
                    date_limite_achat=limite, statut=statut,
                ),
            )
            for ordre, (tnom, prix, stock) in enumerate(types):
                TypeTicket.objects.update_or_create(evenement=ev, nom=tnom, defaults=dict(prix=Decimal(prix), stock=stock, ordre=ordre))
            evenements.append(ev)

        self.stdout.write(self.style.MIGRATE_HEADING("Commandes, paiements et tickets"))
        publies = [e for e in evenements if e.statut == "publie"]
        nb_commandes = 0
        for acheteur in specs:
            for ev in random.sample(publies, k=2):
                tt = random.choice(list(ev.types_tickets.all()))
                if Commande.objects.filter(acheteur=acheteur, tickets__type_ticket=tt).exists():
                    continue
                items = [PanierItem(tt, random.choice([1, 1, 2]))]
                # Un ticket sur deux est réservé pour un ami (sauf billet « table » trop cher).
                if random.random() < 0.5 and tt.prix < 50000:
                    ami = random.choice(SPECTATEURS)
                    items = [PanierItem(tt, 1, {"prenom": ami["prenom"], "nom": ami["nom"], "contact": ami["email"], "sexe": ami["sexe"]})]
                try:
                    commande = creer_commande(acheteur, items, moyen="mtn_momo")
                    lancer_paiement(commande, "mtn_momo", acheteur.telephone_complet)
                    nb_commandes += 1
                except Exception as exc:  # stock épuisé : on ignore proprement
                    self.stdout.write(self.style.WARNING(f"  ignoré : {exc}"))

        # Une commande en attente pour montrer le statut « À payer ».
        ev = publies[0]
        tt = ev.types_tickets.first()
        if tt and not Commande.objects.filter(acheteur=specs[-1], statut="en_attente").exists():
            creer_commande(specs[-1], [PanierItem(tt, 1)], moyen="")

        self.stdout.write(self.style.MIGRATE_HEADING("Retraits"))
        for org_key in ["orga.vibes", "orga.lagune"]:
            org = orgas[org_key]
            if org.solde_disponible > 20000 and not org.retraits.exists():
                Retrait.objects.create(organisateur=org, montant=Decimal("20000"), moyen="mtn_momo", numero_compte=org.telephone, statut=Retrait.Statut.PAYE)

        self.stdout.write(self.style.MIGRATE_HEADING("Cartes de visite"))
        for prefixe, entreprise, contact, poste, tel, mail, site, adresse, slogan, theme in CARTES:
            owner = _email_vers_user(prefixe)
            if owner is None or CarteVisite.objects.filter(utilisateur=owner, nom_entreprise=entreprise).exists():
                continue
            CarteVisite.objects.create(
                utilisateur=owner, theme=theme, nom_entreprise=entreprise, nom_contact=contact, poste=poste,
                telephone=tel, email=mail, site_web=site, adresse=adresse, slogan=slogan,
                paye=True, genere_le=timezone.now(),
                paiement=Paiement.objects.create(utilisateur=owner, objet=Paiement.Objet.CARTE, montant=100, fournisseur="simulation", statut="reussi", termine_le=timezone.now()),
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nDémo prête : {len(ORGANISATEURS)} organisateurs, {len(SPECTATEURS)} spectateurs, "
            f"{len(evenements)} événements, {Ticket.objects.count()} tickets, {Retrait.objects.count()} retrait(s).\n"
            f"Mot de passe de tous les comptes de démo : {MOT_DE_PASSE}\n"
            f"Organisateur : orga.vibes@novatickets.demo · Spectateur : aicha.mensah@novatickets.demo"
        ))

    def _user(self, email, role, prenom, nom, pays, tel, sexe="", profession=""):
        from apps.core.countries import get_pays

        user, created = User.objects.get_or_create(
            email=email,
            defaults=dict(username=email.split("@")[0], first_name=prenom, last_name=nom, role=role,
                          pays=pays, indicatif=get_pays(pays).indicatif_affiche, telephone=tel, sexe=sexe, profession=profession),
        )
        if created:
            user.set_password(MOT_DE_PASSE)
            user.save()
        return user

    def _reset(self):
        """Supprime la démo dans l'ordre des clés PROTECT (enfants avant parents)."""
        from apps.payments.models import Paiement as P

        self.stdout.write("Suppression des données de démo…")
        demo = User.objects.filter(email__endswith="@novatickets.demo")
        CarteVisite.objects.filter(utilisateur__in=demo).delete()
        Ticket.objects.filter(commande__acheteur__in=demo).delete()
        Commande.objects.filter(acheteur__in=demo).delete()
        Retrait.objects.filter(organisateur__in=demo).delete()
        P.objects.filter(utilisateur__in=demo).delete()
        Evenement.objects.filter(organisateur__in=demo).delete()
        demo.delete()
