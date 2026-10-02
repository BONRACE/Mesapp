# NovaTickets 🎟️✦

Plateforme de billetterie événementielle premium — Django, style Neumorphism / Glassmorphism (dark mode, néon), pensée pour le marché béninois.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data      # crée des comptes + événements + billets fictifs
python manage.py runserver
```

Ouvre http://127.0.0.1:8000

## Comptes de démonstration (mot de passe : `nova2026`)

| Rôle          | Identifiant        |
|---------------|---------------------|
| Organisateur  | afrobeats_events     |
| Organisateur  | tech_hub_bj          |
| Spectateur    | bonrace               |
| Spectateur    | aicha_d, koffi_m, ruth_a, fabrice_k |

## Structure

```
accounts/   -> Utilisateur custom (spectateur / organisateur), inscription, profil
events/     -> Événements, types de billets (formset dynamique), dashboard organisateur
tickets/    -> Billet, QR code stylisé, génération PDF "boarding pass premium"
templates/  -> Toutes les vues (base.html = thème glassmorphism global)
core_views.py -> Page d'accueil + redirection dashboard selon le rôle
```

## Fonctionnalités livrées

- Profil spectateur : nom, prénoms, sexe, profession, photo (avatar modifiable)
- Dashboard spectateur : billets à venir / historique, bouton PDF, billet numérique interactif
- Dashboard organisateur : stats globales (événements, billets vendus, revenu), bouton "Publier"
- Formulaire de publication d'événement : visuel, dates début/fin, date limite d'achat, heure,
  logo, types de billets dynamiques (nom, prix, stock) via formset ajout/suppression
- Billet "boarding pass premium" (web + PDF) : nom/prénom, sexe, photo, logo plateforme,
  logo organisateur, QR code stylisé (modules arrondis, néon), type de billet, nom événement
- Données fictives réalistes prêtes à l'emploi (`seed_data`)

## Prochaines étapes suggérées

- Paiement réel (CinetPay / FedaPay / MTN-Moov Money)
- Scanner QR (PWA) côté organisateur pour le contrôle d'accès à l'entrée
- Export CSV des participants, emails de confirmation
