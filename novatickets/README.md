# NovaTickets — billetterie en ligne (Django)

Plateforme de billetterie pour le Bénin et l'Afrique de l'Ouest : paiement en FCFA (mobile money), tickets « boarding pass » avec QR code, espace spectateur et organisateur, retraits, reçu e-mail automatique et créateur de cartes de visite payant (100 FCFA).

**Stack** : Django 5 · templates Django + Tailwind CSS (déjà compilé) · SQLite · Pillow / ReportLab / qrcode.

## Installation rapide

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # données de démonstration (≈ 20 s)
python manage.py runserver
```
Ouvrez http://127.0.0.1:8000. Les e-mails de reçu s'affichent dans le terminal du serveur (mode console).

- `python manage.py seed_demo --reset` vide la base puis recrée la démo.
- `python manage.py test` lance les 36 tests (inscription, achat, paiement, tickets, reçu, retraits, cartes, permissions).

## Comptes de démonstration

Mot de passe de tous les comptes `@demo.nt` : **`NovaTickets2026!`**

| Rôle | E-mail | Pays |
|---|---|---|
| Organisateur | orga.cotonou@demo.nt (Cotonou Live Productions) | Bénin |
| Organisateur | orga.abidjan@demo.nt (Lagune Events) | Côte d'Ivoire |
| Organisateur | orga.dakar@demo.nt (Teranga Culture) | Sénégal |
| Spectateur | spectateur1@demo.nt … spectateur5@demo.nt | Bénin (1-3), Côte d'Ivoire (4), Sénégal (5) |
| Admin Django (`/admin/`) | admin@novatickets.bj / `Admin2026!` | — |

Le seed crée 8 événements (dont 1 brouillon et 2 passés), des commandes payées, des tickets (dont un cadeau pour un ami et un déjà utilisé), 3 retraits et 3 cartes de visite (2 payées, 1 à payer).

## Parcours à tester

1. **Inscription** : `/compte/inscription/` → pays (drapeau + indicatif dynamique), téléphone mobile obligatoire, validé selon le pays.
2. **Achat** : spectateur → événement → « Acheter » → paiement (mobile money selon le pays) → ticket + PDF + reçu e-mail (dans le terminal).
3. **Pour un ami** : case « Réserver pour un ami » à l'achat (spectateur ou organisateur) ; le ticket est au nom de l'ami et lui est envoyé par e-mail.
4. **Organisateur** : tableau de bord, création d'événement (types de tickets dynamiques), bouton « Publier », retrait des gains (`/paiement/retraits/`).
5. **Règle** : un organisateur ne peut pas acheter pour son propre événement, mais peut pour ceux des autres.
6. **Carte de visite** : `/cartes/` → modèle, formulaire, aperçu en direct, paiement de 100 FCFA → PDF et PNG HD (aucune génération sans paiement validé).
7. **Contrôle à l'entrée** : le QR code ouvre `/billets/verifier/<jeton>/` ; l'organisateur de l'événement y valide l'entrée.

## Logo

Remplacez `static/img/logo.png` (logo complet, ~980×240) et `static/img/logo-mark.png` (pastille « N » carrée, ~220×220, utilisée au centre des QR codes) par vos fichiers : navbar, authentification, tickets, PDF et e-mails les reprennent automatiquement. Les fichiers fournis sont des **logos provisoires** (`scripts/make_placeholder_logo.py`).

## Paiement

- `PAYMENT_PROVIDER=simulation` (défaut) : aucune transaction réelle. Un numéro se terminant par **00** simule un refus.
- Vraie passerelle (CinetPay, FedaPay, KKiaPay, Stripe…) : créez une sous-classe de `PaymentProvider` dans `payments/providers.py` (`charge`, `payout`), ajoutez-la à `PROVIDERS`, puis `PAYMENT_PROVIDER=<code>`. Si la passerelle confirme par webhook, `charge` renvoie `pending` et le webhook appelle `payments.services.complete_payment(payment)`.
- Moyens par pays : `payments/methods.py` (Bénin : MTN MoMo, Moov Money, Celtiis Cash ; + carte bancaire).
- Commission : `PLATFORM_COMMISSION_PERCENT` (défaut 5 %). Solde organisateur = ventes − commission − retraits.
- Autres variables : `BUSINESS_CARD_PRICE` (100), `MIN_WITHDRAWAL` (500).

## E-mails

Le reçu part **automatiquement** dès qu'un paiement passe à « validé » (signal `payment_succeeded`, exécuté après validation de la transaction ; un échec d'e-mail n'annule jamais l'achat). Il reprend votre maquette : logo centré + date, logos plateforme/événement, « Merci pour votre achat ! », événement, infos du spectateur, encadré du ticket, signature de l'organisateur avec tampon « vérifié par », « Powered by » et petit QR code. Les tickets PDF sont joints.

- Développement : `EMAIL_MODE=console` (défaut) ou `file` (dossier `sent_emails/`).
- Production : `EMAIL_MODE=smtp` + `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, et `SITE_URL` (URL publique encodée dans les QR codes).

## Production

`DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_ORIGINS`, PostgreSQL si besoin, `python manage.py collectstatic`, et servir `/media/` via votre serveur web.

## Structure

```
config/     réglages, urls
core/       accueil, pays/téléphones, permissions, seed_demo, filtres de gabarit
accounts/   utilisateur (spectateur / organisateur), inscription, profil
events/     événements, types de tickets, espace organisateur
tickets/    commandes, tickets, PDF « boarding pass », QR, e-mail de reçu
payments/   paiements, couche provider, retraits
cards/      cartes de visite (6 modèles, aperçu en direct, PDF/PNG)
templates/ static/   gabarits, CSS Tailwind compilé, JS, polices, drapeaux
```

Modifier le design : `npm install && npm run build:css` (Node requis uniquement pour recompiler Tailwind).
