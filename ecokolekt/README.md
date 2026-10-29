# EcoKolekt — gestion et valorisation des déchets

Application web multi-rôles (Django + SQLite) qui relie **producteurs**, **transporteurs / collecteurs** et **grossistes / centres de recyclage**.

| Module | Où | Ce qu'il fait |
|---|---|---|
| Authentification OTP | `accounts/` | Connexion par numéro de téléphone, code à 6 chiffres haché, limites d'essais et d'envois |
| Tableaux de bord | `core/` | Un tableau de bord par rôle, KPI calculés en base |
| Sites & enlèvements | `operations/` | Sites géolocalisés (latitude / longitude), demandes d'enlèvement, acceptation |
| Routage | `operations/routing.py` | Recherche dans un rayon (filtre SQL + Haversine), tournée optimisée (plus proche voisin + 2-opt), replanification |
| Traçabilité QR | `traceability/` | Lots, QR signés (HMAC), chaîne de hachage des événements, page de provenance publique |
| Marketplace B2B | `marketplace/` | Offres liées aux lots, réservation de stock (verrou), commission 5 % |

Le paiement en ligne n'est pas encore branché : une commande réserve le stock et reste « en attente de paiement » jusqu'à l'intégration de FedaPay.

## Installation

Aucune base serveur ni bibliothèque géospatiale n'est nécessaire : la base est un fichier SQLite (`db.sqlite3`), créé automatiquement.

```bash
python -m venv env && source env/bin/activate      # Windows : env\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # adapter si besoin
python manage.py migrate
python manage.py createsuperuser                    # numéro de téléphone + mot de passe (admin uniquement)
python manage.py runserver
```

Les migrations sont déjà fournies. Si vous modifiez un modèle, lancez `python manage.py makemigrations` avant `migrate`.

En développement, les codes OTP sont écrits dans les logs du serveur (`SMS_BACKEND=console`).

Tests :

```bash
python manage.py test core
```

## Architecture

```
ecokolekt/            configuration (settings, urls, wsgi)
accounts/             User (téléphone + rôle), OTPCode, backend OTP, décorateur role_required
core/                 landing, routeur de tableaux de bord par rôle, tests
operations/           WasteCategory, Site (latitude / longitude), PickupRequest, Route, routing.py
traceability/         WasteBatch (UUID + code), TrackingEvent (chaîne de hachage), services QR
marketplace/          Listing, Order, règles de stock, commission, mark_paid (point d'entrée FedaPay)
templates/            base Tailwind + pages par module (partials/form_fields.html réutilisé)
```

### Parcours
1. **Inscription** : numéro → code SMS → profil et rôle (`/compte/connexion/`).
2. **Producteur** : crée un site de production, demande un enlèvement sur une fenêtre horaire.
3. **Collecteur** : voit les demandes dans son rayon, les accepte, sélectionne celles à tourner, obtient un itinéraire optimisé, valide chaque collecte avec le poids réel → un lot est créé avec son QR.
4. **Recycleur** : scanne le QR, enregistre la réception, la valorisation, publie une offre liée au lot.
5. **Acheteur** : commande (stock réservé). Le passage à « payée » se fera via `marketplace.services.mark_paid` depuis le webhook FedaPay.

## Sécurité
- OTP : code aléatoire, seule l'empreinte HMAC est stockée, usage unique, expiration 5 min, 5 essais max, 5 envois par heure.
- QR : jeton signé (`django.core.signing`) ; un UUID falsifié est refusé.
- Traçabilité : chaque événement référence l'empreinte du précédent ; `verify_chain` détecte toute altération.
- Stock : réservation dans une transaction avec verrou de ligne (pas de survente).

## Limites actuelles et prochaines étapes
- **Géographie** : les distances sont calculées à vol d'oiseau (Haversine) et la recherche par rayon se fait par filtre rectangulaire puis calcul exact. Pour des requêtes spatiales à grande échelle, revenir à PostgreSQL + PostGIS.
- **Routage routier** : pour des durées réelles, remplacer `distance_matrix` par un appel à OSRM ou OpenRouteService.
- **Paiement FedaPay** : créer la transaction, puis un webhook qui vérifie la signature et le montant, puis appelle `mark_paid`. Confirmer les endpoints et l'en-tête de signature dans la documentation FedaPay.
- **SMS** : brancher le fournisseur retenu dans `accounts/sms.py` (`HttpSMS` est un squelette).
- **CSS** : Tailwind est chargé par CDN pour le développement ; en production, compiler Tailwind (CLI).
- **Déploiement** : passer `DJANGO_DEBUG=0`, définir un `DJANGO_SECRET_KEY` réel et configurer `DJANGO_ALLOWED_HOSTS`.
