"""Tests des règles métier critiques. Lancer : python manage.py test tests"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.forms import InscriptionSpectateurForm
from apps.accounts.models import Role, User
from apps.events.models import Evenement, TypeTicket
from apps.payments.models import Paiement
from apps.payments.services import PanierItem, calculer_commission, confirmer_paiement, creer_commande, lancer_paiement
from apps.tickets.models import Commande


def _user(email, role=Role.SPECTATEUR, pays="BJ", tel="97000001"):
    return User.objects.create_user(
        username=email.split("@")[0], email=email, password="x-test-123",
        first_name="Test", last_name="User", role=role, pays=pays, indicatif="+229", telephone=tel,
    )


class CommissionTests(TestCase):
    def test_commission_5_pourcent(self):
        commission, net = calculer_commission(Decimal("5000"), taux=5)
        self.assertEqual(commission, Decimal("250"))
        self.assertEqual(net, Decimal("4750"))


class RegleAchatTests(TestCase):
    def setUp(self):
        self.orga = _user("orga@test.demo", Role.ORGANISATEUR)
        self.autre = _user("autre@test.demo", Role.ORGANISATEUR)
        self.ev = Evenement.objects.create(
            organisateur=self.orga, nom="Test Fest", date_debut=timezone.localdate() + timedelta(days=5),
            heure_debut="18:00", date_fin=timezone.localdate() + timedelta(days=6),
            date_limite_achat=timezone.now() + timedelta(days=4), statut="publie",
        )
        self.tt = TypeTicket.objects.create(evenement=self.ev, nom="Standard", prix=Decimal("5000"), stock=3)

    def test_organisateur_ne_peut_pas_acheter_ses_propres_tickets(self):
        with self.assertRaises(ValidationError):
            creer_commande(self.orga, [PanierItem(self.tt, 1)], moyen="simulation")

    def test_organisateur_peut_acheter_chez_un_autre(self):
        commande = creer_commande(self.autre, [PanierItem(self.tt, 1)], moyen="simulation")
        self.assertEqual(commande.total, Decimal("5000"))

    def test_stock_respecte(self):
        with self.assertRaises(ValidationError):
            creer_commande(self.autre, [PanierItem(self.tt, 4)], moyen="simulation")

    def test_paiement_simulation_emet_et_confirme(self):
        commande = creer_commande(self.autre, [PanierItem(self.tt, 1)], moyen="simulation")
        lancer_paiement(commande, "simulation", "+22997000001")
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.PAYE)
        ticket = commande.tickets.first()
        self.assertEqual(ticket.commission, Decimal("250"))
        self.assertEqual(ticket.montant_net_organisateur, Decimal("4750"))

    def test_confirmation_idempotente(self):
        commande = creer_commande(self.autre, [PanierItem(self.tt, 1)], moyen="simulation")
        p = Paiement.objects.create(utilisateur=self.autre, objet="commande", commande=commande,
                                    montant=commande.total, fournisseur="simulation")
        confirmer_paiement(p)
        confirmer_paiement(p)  # un second appel ne doit ni planter ni renvoyer le reçu
        p.refresh_from_db()
        self.assertEqual(p.statut, "reussi")


class InscriptionTelephoneTests(TestCase):
    base = {"first_name": "Kossi", "last_name": "A", "email": "k@test.demo", "sexe": "H",
            "profession": "Dev", "password1": "Motdepasse!2026", "password2": "Motdepasse!2026"}

    def test_numero_beninois_valide(self):
        form = InscriptionSpectateurForm({**self.base, "pays": "BJ", "telephone": "97 00 00 01"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_numero_trop_court_refuse(self):
        form = InscriptionSpectateurForm({**self.base, "pays": "BJ", "telephone": "9700"})
        self.assertFalse(form.is_valid())
        self.assertIn("telephone", form.errors)

    def test_telephone_obligatoire(self):
        form = InscriptionSpectateurForm({**self.base, "pays": "BJ", "telephone": ""})
        self.assertFalse(form.is_valid())
