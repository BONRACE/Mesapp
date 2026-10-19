# EcoKolekt — gestion de déchets multi-rôles

Application de collecte des déchets pour Cotonou (Bénin) : les ménages demandent une collecte, le collecteur le plus
proche la prend en charge sur une tournée optimisée, valide le passage en scannant un QR code signé, et les
matières triées se revendent sur un marché en ligne payé en Mobile Money.

- **Backend** : Django 5 + Django REST Framework, GeoDjango, PostgreSQL 16 + PostGIS, JWT.
- **Frontend** : application web monopage en JavaScript natif (sans build), Leaflet pour les cartes. Palette vert `#0B4A32` / or `#D4A62F`.
- **Rôles** : ménage (`citizen`), collecteur (`collector`), recycleur/acheteur (`recycler`), administration (`admin`).

```
backend/    API Django (accounts, waste, routing, marketplace, payments) + 61 tests
frontend/   index.html (accueil) · app.html (inscription OTP + dashboards) · js/ · css/ · vendor/leaflet
deploy/     Dockerfile, docker-compose.yml (PostGIS + API + nginx), nginx.conf
.env.example
```

## Démarrage rapide

### Avec Docker
```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml --env-file .env up --build
# http://localhost:8080      (docs de l'API : http://localhost:8080/api/docs/)
docker compose -f deploy/docker-compose.yml exec api python manage.py seed_demo   # comptes de démonstration
```

### Sans Docker
Prérequis : Python 3.12+, PostgreSQL avec l'extension PostGIS, et les bibliothèques GDAL/GEOS/PROJ
(`sudo apt install gdal-bin postgresql-16-postgis-3`).
```bash
createdb ecokolekt && psql ecokolekt -c "CREATE EXTENSION postgis"
cd backend && pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver                       # API sur :8000
cd ../frontend && python3 -m http.server 8080    # frontend sur :8080
python manage.py test                            # depuis backend/
```

### Comptes de démonstration
En mode démo (`SMS_BACKEND=console`), le code OTP s'affiche à l'écran (« Mode démo : code … ») et dans la console du serveur.

| Rôle | Numéro |
|---|---|
| Administration | +229 01 97 00 00 01 |
| Ménages | +229 01 96 00 00 01 · +229 01 61 23 45 67 |
| Collecteurs | +229 01 97 12 34 56 · +229 01 55 12 34 56 |
| Recycleur | +229 01 66 12 34 56 |

Les numéros béninois sont à 10 chiffres (préfixe `01`) ; la saisie est normalisée en E.164 (`+229…`).

## Modules

**Authentification par téléphone + OTP** (`accounts/`) — pas de mot de passe. Code à 6 chiffres, stocké haché (HMAC), valable
5 min, 5 essais maximum, 60 s entre deux envois, 5 envois/heure/numéro, plus un plafond par IP. Le compteur d'essais survit
à l'échec. Inscription en 4 étapes (numéro → code → choix du profil → champs propres au rôle). Collecteurs et recycleurs
sont validés par l'administration (auto-approuvés seulement en démo). L'envoi SMS est un adaptateur HTTP générique
(`accounts/otp.py::send_sms`) à brancher sur votre agrégateur.

**QR codes sécurisés** (`waste/qr.py`) — jeton `EK1.<demande>.<nonce>.<signature>` signé HMAC-SHA256. À la validation, le
serveur vérifie : signature, nonce (régénéré après usage → **usage unique**, un QR photographié ne sert à rien),
collecteur **assigné** à la demande, et **proximité GPS** (≤ `QR_MAX_DISTANCE_M`, 250 m ; les coordonnées sont obligatoires).
Un QR n'expire pas dans le temps : il cesse d'être valable à l'usage ou à l'annulation de la demande.

**Routage GPS dynamique** (`routing/services.py`, `waste/services.py`) — affectation automatique au collecteur en service le
moins chargé puis le plus proche (requête PostGIS `dwithin` + `Distance`). Tournée : matrice de durées (OSRM si `OSRM_URL`,
sinon haversine × 1,3), plus proche voisin + 2-opt, ETA cumulées, alerte de dépassement de capacité, géométrie de l'itinéraire.
Elle est **recalculée à chaque consultation** depuis la dernière position du collecteur, et après chaque scan. Au-delà d'environ
40 arrêts par collecteur, brancher un solveur VRP (OR-Tools, VROOM) derrière `optimize_route`.

**Marché des matières recyclées** (`marketplace/`) — annonces (catégorie, qualité, quantité, prix au kg, localisation),
commandes avec stock réservé 30 min, expiration automatique, commission plateforme (`MARKET_COMMISSION_RATE`, 5 %),
suivi `en attente de paiement → payée → expédiée → livrée`, tableau de revenus vendeur et cours indicatifs.

**Paiements** (`payments/`) — passerelles **FedaPay** et **CinetPay** (Mobile Money + cartes) et une passerelle `mock` de démo.
Principe de sécurité : un webhook ou une URL de retour ne sont jamais crus ; ils déclenchent seulement une relecture du
statut chez la passerelle. Finalisation idempotente, double paiement et paiement tardif sans stock signalés
(`needs_refund`). CinetPay : montant arrondi au multiple de 5 XOF, sous-paiement refusé.

## Modèle de données

| Modèle | Rôle | Champs clés |
|---|---|---|
| `User` | compte (téléphone E.164 unique) | `role`, `is_approved`, `profile_completed`, `eco_points`, `location` (PostGIS) |
| `CollectorProfile` | collecteur | `vehicle_type`, `capacity_kg`, `is_on_duty`, `current_location`, `last_seen` |
| `RecyclerProfile` | acheteur | `company_name`, `address` |
| `OTPCode` | codes à usage unique | `phone`, `code_hash`, `expires_at`, `attempts`, `consumed_at` |
| `WasteCategory` | types de déchets | `code`, `points_per_kg`, `is_recyclable`, `color` |
| `CollectionPoint` | bacs, points d'apport, centres | `kind`, `location`, `categories`, `opening_hours` |
| `PickupRequest` | demande de collecte | `citizen`, `collector`, `category`, `location`, `estimated/actual_weight_kg`, `status`, `qr_nonce`, `qr_used_at`, `points_awarded` |
| `Route` / `RouteStop` | tournée d'un collecteur | `geometry` (GeoJSON), `total_distance_m`, `engine` ; `sequence`, `eta_seconds`, `over_capacity` |
| `Listing` | annonce du marché | `seller`, `category`, `quantity_kg`, `unit_price`, `grade`, `location` |
| `Order` | commande | `buyer`, `seller`, `quantity_kg`, `unit_price` (figé), `total`, `commission`, `status` |
| `Payment` | tentative de paiement | `order`, `provider`, `provider_ref`, `amount`, `status`, `needs_refund` |

Statuts d'une demande : `pending → assigned → en_route → collected` (ou `cancelled`).
Toutes les colonnes de position sont des `geography(Point, 4326)` indexées (GiST).

## Endpoints essentiels

Préfixe `/api`. Toutes les routes exigent un JWT (`Authorization: Bearer …`) sauf mention contraire.

| Domaine | Méthode · chemin | Rôle |
|---|---|---|
| Auth | `POST /auth/otp/request/` · `POST /auth/otp/verify/` · `POST /auth/token/refresh/` | public, throttlé |
| Profil | `GET/PATCH /me/` · `POST /me/location/` (service + position GPS) | tous · collecteur |
| Collectes | `GET/POST /waste/pickups/` · `GET /waste/pickups/{id}/` | ménage crée, chacun voit les siennes |
| | `GET /waste/pickups/{id}/qr/` (PNG) · `/tracking/` · `POST …/cancel/` | ménage |
| | `GET /waste/pickups/available/` · `POST …/{id}/accept/` · `…/start/` · `POST /waste/pickups/scan/` | collecteur |
| | `GET /waste/pickups/summary/` · `POST /waste/pickups/auto-assign/` | tous · admin |
| Référentiels | `GET /waste/categories/` · `GET /waste/points/?lat=&lng=&radius_km=` | authentifié |
| Routage | `GET/POST /routing/route/` (recalcul, origine optionnelle) · `GET /routing/collectors/live/` | collecteur · admin |
| Marché | `GET/POST /market/listings/` · `GET/PATCH/DELETE /market/listings/{id}/` | vendeur écrit |
| | `GET/POST /market/orders/` · `POST …/{id}/ship/` · `…/deliver/` · `…/cancel/` | acheteur · vendeur |
| | `GET /market/prices/` · `GET /market/earnings/` | cours · vendeur |
| Paiements | `POST /payments/initiate/` · `GET /payments/{id}/` | acheteur |
| | `GET/POST /payments/webhook/{fedapay\|cinetpay}/` | public (relecture serveur) |
| Admin | `GET /admin/stats/` · `GET /admin/users/` · `POST /admin/users/{id}/approve/` | administration |

Documentation interactive : `/api/docs/` (schéma `/api/schema/`). Plusieurs vues sont des `APIView` sans serializer déclaré :
leur schéma est partiel, la table ci-dessus fait foi.

## Passer en production

Avec `DJANGO_DEBUG=0` le serveur **refuse de démarrer** tant que la configuration est une configuration de démonstration :
clé secrète ≥ 32 caractères, `ALLOWED_HOSTS` explicite, `SMS_BACKEND=http`, passerelle réelle (`fedapay` ou `cinetpay`).
Il faut aussi : HTTPS, `BACKEND_URL` public pour les `notify_url`, `AUTO_APPROVE_PROFESSIONALS=0`, sauvegardes PostgreSQL,
un cache Redis partagé si vous lancez plusieurs processus (les limites OTP/IP utilisent le cache de Django).

## Limites connues — à traiter avant le lancement

- **Reversement aux vendeurs non automatisé** : les paiements sont encaissés et la commission calculée, mais aucun portefeuille ni
  virement (API de décaissement FedaPay/CinetPay) n'est implémenté ; `/market/earnings/` indique seulement ce qui est dû.
- **Collecte gratuite** : pas de frais de collecte facturés aux ménages ; ils gagnent des points éco (non convertibles).
- **FedaPay et CinetPay** : intégrations écrites d'après leur documentation et testées avec des réponses simulées. Les valider
  sur les comptes de test des deux fournisseurs (formats de réponse, signature des webhooks) avant d'encaisser.
- **Jetons JWT en `localStorage`** : acceptable pour une V1, mais exposé en cas de faille XSS ; envisagez des cookies `HttpOnly`.
- **Image Docker non construite** dans l'environnement de rédaction (la syntaxe du compose est validée) : un premier `up --build` est à prévoir.
- Fonts Google et tuiles OpenStreetMap chargées depuis Internet ; pour une forte charge, utiliser un fournisseur de tuiles dédié.
