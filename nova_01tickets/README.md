# NovaTickets — billetterie en ligne (Django)

Plateforme de billetterie blanc/vert, pensée **ordinateur ET smartphone**.

## Lancer le projet

```bash
python -m venv venv && source venv/bin/activate     # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # comptes + événements + ventes de démonstration
python manage.py runserver 0.0.0.0:8000
```

Ouvrir http://127.0.0.1:8000. **Tester sur smartphone** : connectez le téléphone au même Wi-Fi,
ouvrez `http://<IP-de-votre-PC>:8000` (et mettez `SITE_URL` dans `config/settings.py` à cette adresse
pour que les QR codes pointent vers elle).

Comptes de démo (mot de passe `demo1234`) :
- Organisateurs : `orga_benin`, `orga_ci`
- Spectateurs : `spec_marie`, `spec_jean`, `spec_fatou`

Tests : `python manage.py test core`

## Logo
Le fichier `static/img/logo.png` est un logo provisoire. **Remplacez-le par votre logo NovaTickets**
(même nom, PNG de préférence : indispensable pour l'e-mail et le PDF).

## Ce qui s'adapte à l'écran

| Élément | Smartphone | Ordinateur |
|---|---|---|
| Navigation | barre fixe en bas (Accueil / Billets ou Tableau / Profil) | menu en haut |
| Tableaux de bord | blocs empilés, tableaux transformés en cartes | menu latéral + vrais tableaux |
| Statistiques organisateur | 2 colonnes | 4 colonnes |
| Fiche événement | bouton « Voir les billets » fixe en bas | colonne d'achat collante à droite |
| Paiement | récapitulatif en haut | récapitulatif à droite |
| Billet | vertical, QR code sous les infos | horizontal « boarding pass » avec souche |
| Formulaires | 1 colonne, champs 16 px (pas de zoom iPhone), boutons ≥ 44 px | 2 colonnes |

## Fonctionnalités
- Inscription spectateur / organisateur : liste de **tous les pays** avec drapeau + indicatif (ex. 🇧🇯 +229) qui se met à jour, **téléphone mobile obligatoire**.
- Moyens de paiement selon le **pays de l'acheteur** (`core/countries.py`), commission de **5 %** (`PLATFORM_COMMISSION_RATE`).
- Un organisateur **ne peut pas acheter pour son propre événement** (mais peut acheter chez les autres).
- Organisateur : statistiques, création/modification d'événement (types de tickets dynamiques), bouton **Publier**, **retrait** des fonds vers des moyens locaux (mobile money).
- Billet « boarding pass » : nom, prénoms, sexe, photo, logos plateforme + organisateur, QR code stylisé, type de ticket, événement. Téléchargement **PDF**.
- Page de contrôle du QR (`/verifier/<code>/`) : l'organisateur valide l'entrée.
- **E-mail reçu** HTML automatique après paiement validé (en développement : affiché dans la console).

## À brancher en production
- **Paiement réel** : remplacer `charge()` dans `orders/services.py` par FedaPay / KkiaPay / CinetPay.
  En démo, un numéro se terminant par `0000` simule un refus.
- **E-mails réels** : configurer `EMAIL_BACKEND` SMTP dans `config/settings.py`.
- `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, base PostgreSQL, hébergement des fichiers média.
- Les retraits sont enregistrés « En cours » : le versement réel se fait via l'admin (`/admin/`, créez un superuser) ou une API de paiement sortant.
