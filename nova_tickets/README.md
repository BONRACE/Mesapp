# NovaTickets — billetterie en ligne (Django)

Plateforme de billetterie blanc/vert pour le marché béninois et ouest-africain : spectateurs, organisateurs,
paiement Mobile Money (push + webhook), billets PDF « boarding pass » avec QR code, scanner caméra, cartes de visite
numériques, analytiques en direct et retraits multi-canaux. Django uniquement (SQLite par défaut).

## Lancer le projet

> Avant de démarrer : `cp .env.example .env` puis renseignez le fichier `.env` (voir « Configuration .env » plus bas). Un `.env` d'exemple est déjà fourni.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate          # à relancer après chaque mise à jour (signature, styles de carte…)
python manage.py seed_demo --reset  # données de démo ; --reset = dates fraîches (les dates sont relatives au jour du lancement)
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000 — tous les comptes de démo ont le mot de passe `demo1234` :

| Rôle | E-mail |
|---|---|
| Organisateur (Bénin) | orga.cotonou@demo.test |
| Organisateur (Côte d'Ivoire) | orga.abidjan@demo.test |
| Spectateurs | fan.benin@demo.test · fan.ci@demo.test · fan.france@demo.test · fan.togo@demo.test |

Tests : `python manage.py test` (120+ tests : paiements, webhook, commandes, scanner, cartes, PDF, analytiques, retraits).

## Mise à jour d'une ancienne version (affichage cassé ?)
1. Remplacer **tout** le dossier du projet (surtout `static/` et `templates/`), pas seulement quelques fichiers.
2. `python manage.py migrate` puis `python manage.py seed_demo --reset` (nouvelles bannières sans texte).
3. Actualiser le navigateur sans cache (**Ctrl + F5**). Les fichiers statiques portent désormais `?v=<date>` : le CSS périmé n'est plus servi.

## Les 6 modules

| # | Module | Code | URL |
|---|---|---|---|
| 1 | **Mobile Money** MTN / Moov (push USSD, webhook signé, statuts) | `payments/` + `orders/services.py` | `/paiement/…` |
| 2 | **Scanner caméra** (html5-qrcode embarqué, saisie manuelle, journal) | `scanner/` | `/organisateur/scanner/` |
| 3 | **Cartes de visite** liées aux billets (page publique, vCard, QR, badge participant) | `cards/` | `/carte/…` |
| 4 | **PDF** : billet, billets groupés, reçus de commande et de transaction | `core/pdf.py`, `orders/services.py` | `/billets/<réf>/pdf/`, `/commandes/<réf>/recu.pdf` |
| 5 | **Analytiques** temps réel (ventes, revenus, remplissage, affluence) | `analytics/` | `/organisateur/analytiques/` |
| 6 | **Moyens de retrait** (Mobile Money par pays, banque, PayPal) | `payouts/` | `/organisateur/moyens-retrait/` |

### 1. Mobile Money
- Parcours : commande → choix MTN / Moov + numéro → `Transaction` PENDING → push sur le téléphone → page de suivi (rafraîchie
  toutes les 4 s) → le **webhook** confirme → billets créés + reçu e-mail. Le montant vient toujours de la commande, jamais du navigateur.
- Webhook : `POST /paiement/webhook/`, JSON `{"reference","status","transaction_id","amount"}`, en-tête `X-Signature` =
  HMAC-SHA256 hex du corps brut avec `MOMO_WEBHOOK_SECRET`. Idempotent (rejeu sans effet), refuse un montant incohérent,
  une transaction terminée ne change plus. Si le stock est épuisé entre-temps, la commande passe en « À rembourser ».
- Pays en push + webhook : **Bénin, Côte d'Ivoire, Togo, Burkina Faso, Mali, Niger** (zone FCFA/XOF). MTN Cameroun / Ghana
  (autres devises), Orange, Wave, Celtiis et la carte restent simulés (`core/payments.py`, `process_payment`).
- En développement (`DEBUG=True`, mode `simulation`), la page d'attente affiche deux boutons qui rejouent le webhook.
- Brancher une vraie passerelle : `MOMO_GATEWAY_MODE = "live"`, `MOMO_API_BASE_URL`, `MOMO_API_KEY`, et adapter
  `push_payment()` dans `payments/services.py` au contrat de l'agrégateur (FedaPay, KkiaPay, CinetPay…).

### 2. Scanner
- La caméra exige **HTTPS** (ou `localhost`). Sinon, la saisie manuelle de la référence reste disponible.
- Un billet ne peut être validé qu'une fois (verrou en base) ; chaque contrôle est journalisé (`ScanLog`) et alimente l'affluence.
- Seul l'organisateur de l'événement peut scanner ses billets.

### 3. Cartes de visite
- **7 mises en page** (Classique, Centré, Deux volets, Minimal, Affiche, et deux styles « Pagne » inspirés de la carte de référence : motif wax, fond crème,
  cadre QR « Scannez-moi ». « Pagne recto/verso » se retourne d'un clic, « Pagne verso » affiche contacts + QR). Les motifs viennent de `cards/palettes.py` (SVG dans `static/img/wax/`) × **10 couleurs** (Vert Nova, Forêt, Menthe, Océan, Bleu Nova, Soleil,
  Violet, Rose, Or, Graphite), avec aperçu en direct dans le formulaire. Tout est dans `static/css/card.css` : ajouter une couleur = une
  ligne `.t-xxx {…}` + un choix dans `cards/models.py::Theme`.
- Une carte par utilisateur, activée par un paiement Mobile Money (`BUSINESS_CARD_PRICE`, 100 FCFA ; `0` = gratuit).
- Depuis le billet : lien, QR, bouton Partager et fichier `.vcf`. Le lien porte `?billet=<réf>` : la page publique affiche alors un
  badge « Participant · événement », **vérifié côté serveur** (billet payé appartenant bien au propriétaire de la carte).

### 4. Reçu (e-mail + PDF)
- Envoyé **automatiquement** dès que le paiement est validé (webhook Mobile Money, paiement simulé, activation de carte) : e-mail HTML
  + reçu PDF + un billet PDF par place. Mise en page de la maquette : logo, « Plateforme de Billetterie », date, logos plateforme + événement,
  « Merci pour votre achat ! », informations du spectateur, détails du ticket, signature de l'organisateur, « Powered by », réseaux, QR.
- Le PDF et l'e-mail viennent du même dictionnaire (`orders/services.py::receipt_data`) : ils sont toujours identiques.
- La **signature** se règle dans le profil organisateur (nom et fonction) ; à défaut, son nom. Les liens des icônes de réseaux : `SOCIAL_LINKS`
  dans `config/settings.py` (vide = lien vers le site).

### 6. Moyens de retrait
- L'organisateur enregistre jusqu'à 8 canaux (catalogue par pays dans `payouts/catalog.py`), choisit un canal par défaut et retire vers l'un d'eux.
  Les comptes sont masqués dans l'historique. Aucun virement réel n'est émis : brancher l'API de l'opérateur dans `orders/services.py::request_withdrawal`.

## Configuration `.env` (e-mails SMTP, secrets)
Tous les réglages sensibles sont lus dans le fichier `.env` à la racine (jamais publié : il est dans `.gitignore` ; `.env.example` sert de modèle).

| Variable | Exemple | Rôle |
|---|---|---|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | SMTP réel (ou `…filebased.EmailBackend` : e-mails écrits dans `sent_emails/`) |
| `EMAIL_HOST` | `smtp.gmail.com` | serveur SMTP |
| `EMAIL_PORT` | `587` | 587 (TLS) ou 465 (SSL) |
| `EMAIL_HOST_USER` | `votre.adresse@gmail.com` | compte d'envoi |
| `EMAIL_HOST_PASSWORD` | `mot-de-passe-application-16-caracteres` | Gmail : « mot de passe d'application » (validation en 2 étapes requise) |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `True` / `False` | 587 → TLS ; 465 → SSL (un seul des deux) |
| `EMAIL_TIMEOUT` | `10` | délai maximal (s) d'une connexion SMTP |
| `DEFAULT_FROM_EMAIL` | `NovaTickets <votre.adresse@gmail.com>` | expéditeur affiché |

Tant que `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` ont leurs valeurs d'exemple, l'envoi réel est désactivé et les e-mails sont écrits dans `sent_emails/` (aucune erreur). Les autres variables : `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `SITE_URL`, `MOMO_*`, `SUPPORT_EMAIL`, `LEGAL_COMPANY`.

## Commission, navigation, inscription, CGU
- **Commission : 2,5 %** du prix de chaque billet vendu (`PLATFORM_COMMISSION_PERCENT`), prélevée sur le montant reversé à l'organisateur ; l'acheteur ne paie aucun frais en plus. Les commandes déjà payées gardent la commission enregistrée à l'époque.
- **Navigation en bas** : barre fixe sur toute la largeur (`templates/base.html`, `static/css/app.css`) ; sur téléphone, onglets avec icônes (qui défilent s'il y en a plus de 5, cas de l'organisateur).
- **Inscription** : onglets Spectateur / Organisateur, nom d'utilisateur, pays avec drapeau et indicatif, photo. On se connecte avec l'e-mail **ou** le nom d'utilisateur (`accounts/backends.py`).
- **CGU / politique d'utilisation** : `/conditions-generales/` (`templates/core/terms.html`), liée depuis le pied de page et l'inscription. À faire relire par un juriste et à compléter (`LEGAL_COMPANY`, immatriculation, déclaration APDP) avant la mise en service commerciale.

## Mot de passe oublié
- Lien « Mot de passe oublié ? » sur la page de connexion → `/compte/mot-de-passe/oublie/` : saisie de l'e-mail, envoi d'un lien à usage unique
  (valable 1 h, `PASSWORD_RESET_TIMEOUT`), page « Nouveau mot de passe », confirmation. La réponse est la même que l'e-mail existe ou non
  (on ne révèle pas quels comptes existent). En développement, l'e-mail est écrit dans `sent_emails/` ; en production, configurer `EMAIL_BACKEND` (SMTP).

## À personnaliser
- Logo : `static/img/logo.png` (symbole), `logo-horizontal.png` (reçus, e-mails), `logo-full.png` (version verticale complète).
- `config/settings.py` : `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `SITE_URL` (utilisé dans les QR codes), `MOMO_WEBHOOK_SECRET`,
  `EMAIL_BACKEND` (en développement les e-mails sont écrits dans `sent_emails/`).
- Les drapeaux de la page d'inscription viennent d'un CDN (`flag-icons`) : connexion internet requise pour les voir.

## Structure
```
config/      réglages et URLs          accounts/   utilisateurs, inscription, profil
core/        accueil, pays, moyens de paiement, PDF reçu, seed_demo
events/      événements, types de tickets, tableau de bord, retraits
orders/      commandes, billets, PDF billets/reçus, reçu e-mail
payments/    Transaction Mobile Money, webhook, page de suivi
scanner/     contrôle d'entrée         cards/      cartes de visite
analytics/   statistiques en direct    payouts/    moyens de retrait
```
