# NovaTickets — billetterie en ligne (Django)

Plateforme de billetterie blanc/vert pour le marché béninois et ouest-africain :
spectateurs, organisateurs, paiement selon le pays, commission plateforme, retraits, billet « boarding pass » avec QR code, reçu e-mail automatique.

## Lancer le projet

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # données de démonstration (--reset pour repartir de zéro)
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000

| Compte | E-mail | Mot de passe |
|---|---|---|
| Organisateur (Bénin) | orga.cotonou@demo.test | demo1234 |
| Organisateur (Côte d'Ivoire) | orga.abidjan@demo.test | demo1234 |
| Spectateur (Bénin) | fan.benin@demo.test | demo1234 |
| Spectateur (Côte d'Ivoire) | fan.ci@demo.test | demo1234 |
| Spectateur (France) | fan.france@demo.test | demo1234 |
| Spectateur (Togo) | fan.togo@demo.test | demo1234 |

Admin Django : `python manage.py createsuperuser` puis `/admin/`.
Tests : `python manage.py test` (16 tests : commission, règles d'achat, retraits, PDF, e-mail, parcours HTTP).

## Ce qui est inclus

- **Inscription** spectateur (nom, prénoms, sexe, profession, photo) et organisateur (organisation, logo, …).
  Sélecteur de pays avec **drapeau + indicatif dynamique** (+229 pour le Bénin…) et **numéro de mobile obligatoire**, validé selon le pays.
- **Espace spectateur** : billets à venir / historique, vue du billet numérique, téléchargement PDF, profil.
- **Espace organisateur** : statistiques (ventes brutes, commission, net, solde), création/modification d'événements
  (visuel, logo, dates, heure, date limite d'achat, **types de tickets dynamiques** prix + stock), bouton **Publier / Dépublier**,
  **retrait des fonds** vers les moyens locaux du pays de l'organisateur.
- **Achat** : moyens de paiement selon le **pays de l'acheteur**, commission de 5 % (`PLATFORM_COMMISSION_PERCENT`),
  un organisateur **ne peut pas acheter pour son propre événement** (mais peut acheter chez les autres).
- **Billet premium** : nom/prénoms, sexe, photo, logo plateforme, logo organisateur, QR code stylisé, type de ticket, nom de l'événement
  (page web + PDF).
- **Reçu e-mail** automatique après paiement validé (logos, détails, signature organisateur avec cachet « vérifié », QR, billets PDF joints).
  En développement, les e-mails sont écrits dans `sent_emails/` (ouvrir le `.log` ; passer sur SMTP en production).
- **Contrôle d'entrée** : le QR pointe vers `/verification/<référence>/` ; l'organisateur de l'événement peut y valider l'entrée.

## À personnaliser

- **Logo** : remplacer `static/img/logo.png` par le vrai logo NovaTickets (PNG carré, fond transparent). Il est repris partout (site, PDF, e-mail).
- **Paiement** : `core/payments.py` contient une passerelle **simulée** (`process_payment`). Pour la production, y brancher FedaPay / KkiaPay / CinetPay.
  En démo, un numéro Mobile Money finissant par `0000` simule un refus.
- **Retraits** : enregistrés et déduits du solde, mais aucun virement réel n'est émis (même point d'intégration).
- **Moyens par pays** : dictionnaire `BY_COUNTRY` dans `core/payments.py`.
- **Production** : changer `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `SITE_URL` (utilisé dans les QR codes) et `EMAIL_BACKEND` dans `config/settings.py`.
- Les drapeaux utilisent la librairie `flag-icons` chargée depuis un CDN : une connexion internet est nécessaire pour les voir.

## Structure

```
config/      réglages et URLs
core/        accueil, vérification QR, pays + indicatifs, moyens de paiement, filtres, seed_demo
accounts/    utilisateur (spectateur / organisateur), inscription, profil
events/      événements, types de tickets, tableau de bord organisateur, retraits
orders/      commandes, billets, services (paiement, commission, QR, PDF, e-mail)
templates/   pages, e-mail de reçu
static/      CSS, JS (sélecteur pays, formulaire dynamique), logo
```
