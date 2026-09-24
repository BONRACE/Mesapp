import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from events.models import Event, TicketType
from tickets.models import Ticket


class Command(BaseCommand):
    help = "Génère des données fictives réalistes pour NovaTickets."

    def handle(self, *args, **options):
        today = timezone.now().date()

        # --- Organisateurs ---
        org1, _ = User.objects.get_or_create(
            username="afrobeats_events",
            defaults=dict(email="contact@afrobeatsevents.bj", role=User.Role.ORGANISATEUR,
                          nom="Houngbo", prenoms="Serge", sexe="H", profession="Producteur événementiel",
                          nom_structure="Afrobeats Events"))
        org1.set_password("nova2026")
        org1.save()

        org2, _ = User.objects.get_or_create(
            username="tech_hub_bj",
            defaults=dict(email="hello@techhubbenin.bj", role=User.Role.ORGANISATEUR,
                          nom="Assogba", prenoms="Marina", sexe="F", profession="Directrice communication",
                          nom_structure="TechHub Bénin"))
        org2.set_password("nova2026")
        org2.save()

        # --- Spectateurs ---
        spectateurs = []
        data_spectateurs = [
            ("bonrace", "Kpangon", "Bonrace", "H", "Étudiant en informatique"),
            ("aicha_d", "Djossou", "Aïcha", "F", "Designer graphique"),
            ("koffi_m", "Mensah", "Koffi", "H", "Développeur logiciel"),
            ("ruth_a", "Adjovi", "Ruth", "F", "Community manager"),
            ("fabrice_k", "Kiki", "Fabrice", "H", "Entrepreneur"),
        ]
        for username, nom, prenoms, sexe, profession in data_spectateurs:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults=dict(email=f"{username}@example.com", role=User.Role.SPECTATEUR,
                              nom=nom, prenoms=prenoms, sexe=sexe, profession=profession))
            u.set_password("nova2026")
            u.save()
            spectateurs.append(u)

        # --- Événements ---
        e1, _ = Event.objects.get_or_create(
            organisateur=org1, nom="Cotonou Music Night",
            defaults=dict(
                description="Une soirée live avec les meilleurs artistes afrobeats et amapiano du moment, "
                             "au cœur de Cotonou. Ambiance premium, sound system haut de gamme.",
                lieu="Palais des Congrès", ville="Cotonou",
                date_debut=today + datetime.timedelta(days=18),
                date_fin=today + datetime.timedelta(days=18),
                heure_debut=datetime.time(20, 0),
                date_limite_achat=today + datetime.timedelta(days=16),
                statut=Event.Statut.PUBLIE,
            ))
        e2, _ = Event.objects.get_or_create(
            organisateur=org2, nom="Bénin Tech Summit 2026",
            defaults=dict(
                description="Le rendez-vous annuel des développeurs, startups et investisseurs "
                             "de l'écosystème numérique béninois et ouest-africain.",
                lieu="Campus Sèmè City", ville="Sèmè-Podji",
                date_debut=today + datetime.timedelta(days=32),
                date_fin=today + datetime.timedelta(days=33),
                heure_debut=datetime.time(9, 0),
                date_limite_achat=today + datetime.timedelta(days=30),
                statut=Event.Statut.PUBLIE,
            ))
        e3, _ = Event.objects.get_or_create(
            organisateur=org1, nom="Festival Vodún Days",
            defaults=dict(
                description="Célébration culturelle mêlant spectacles traditionnels et performances "
                             "contemporaines, dans une ambiance immersive.",
                lieu="Place de l'Amazone", ville="Ouidah",
                date_debut=today - datetime.timedelta(days=10),
                date_fin=today - datetime.timedelta(days=9),
                heure_debut=datetime.time(16, 0),
                date_limite_achat=today - datetime.timedelta(days=12),
                statut=Event.Statut.TERMINE,
            ))

        # --- Types de billets ---
        def ensure_types(event, types):
            if event.types_billets.exists():
                return list(event.types_billets.all())
            created = []
            for nom, prix, stock, couleur in types:
                created.append(TicketType.objects.create(
                    event=event, nom=nom, prix=prix, quantite_disponible=stock, couleur_badge=couleur,
                    description="Accès général" if nom == "Standard" else "Accès + avantages exclusifs"))
            return created

        types_e1 = ensure_types(e1, [("Early Bird", 5000, 50, "cyan"),
                                      ("Standard", 8000, 200, "violet"),
                                      ("VIP", 20000, 40, "or")])
        types_e2 = ensure_types(e2, [("Standard", 3000, 300, "violet"),
                                      ("VIP", 15000, 60, "or")])
        types_e3 = ensure_types(e3, [("Standard", 4000, 150, "violet"),
                                      ("VIP", 12000, 30, "or")])

        # --- Billets vendus (fictifs) ---
        def ensure_ticket(spectateur, ticket_type):
            ticket, created = Ticket.objects.get_or_create(
                spectateur=spectateur, ticket_type=ticket_type,
                defaults={"statut": Ticket.Statut.VALIDE})
            if created:
                ticket_type.quantite_vendue += 1
                ticket_type.save()
            return ticket

        ensure_ticket(spectateurs[0], types_e1[1])  # Bonrace -> Standard Music Night
        ensure_ticket(spectateurs[0], types_e2[0])  # Bonrace -> Standard Tech Summit
        ensure_ticket(spectateurs[1], types_e1[2])  # Aïcha -> VIP Music Night
        ensure_ticket(spectateurs[2], types_e2[1])  # Koffi -> VIP Tech Summit
        ensure_ticket(spectateurs[3], types_e1[0])  # Ruth -> Early Bird Music Night
        ensure_ticket(spectateurs[0], types_e3[0])  # Bonrace -> Standard Vodún Days (événement passé)
        ensure_ticket(spectateurs[4], types_e3[1])  # Fabrice -> VIP Vodún Days (événement passé)

        self.stdout.write(self.style.SUCCESS(
            "✅ Données fictives créées. Comptes de test (mot de passe: nova2026) :\n"
            "   Organisateurs : afrobeats_events, tech_hub_bj\n"
            "   Spectateurs   : bonrace, aicha_d, koffi_m, ruth_a, fabrice_k"
        ))
