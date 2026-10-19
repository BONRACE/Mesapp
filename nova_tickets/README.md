# NovaTickets — billetterie en ligne (Django)

Plateforme de billetterie blanc/vert, pensée **ordinateur ET smartphone**.

## Lancer le projet

```bash
python -m venv venv && source venv/bin/activate     # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # Windows : copy .env.example .env   (puis adaptez les valeurs)
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
Votre logo NovaTickets est intégré partout : en-tête, connexion/inscription, billet à l'écran, billet PDF
et e-mails. Fichiers dans `static/img/` : `logo-full.png` (vertical), `logo-horizontal.png` (en-tête, billet),
`logo-icon.png` / `favicon.png` (icône d'onglet). Pour le changer, remplacez ces fichiers en gardant leurs noms.
Les liens Facebook / Instagram / X du pied d'e-mail se règlent dans `SOCIAL_LINKS` (`config/settings.py`).

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
- **E-mail reçu** HTML automatique après paiement validé, calqué sur la maquette (logos plateforme + événement, informations du spectateur, détails du ticket, signature de l'organisateur avec cachet « vérifié », « Powered by », réseaux, QR). Les images sont **intégrées au message** : elles s'affichent même sans site en ligne. En développement, l'e-mail s'affiche dans la console.
- **Réserver un billet pour un ami** (spectateurs **et** organisateurs, sur les événements des autres) : case « 🎁 Réserver pour un ami » sur la fiche événement (nom, prénoms, sexe, e-mail, téléphone, photo facultative). Le billet est **au nom de l'ami** (écran, PDF, page de contrôle). Si son e-mail est renseigné, il reçoit automatiquement le(s) billet(s) en **PDF**. L'acheteur garde le reçu et retrouve le billet dans « Mes billets » (page aussi accessible aux organisateurs). Pour plusieurs amis, faites une réservation par ami.
- **Carte de visite d'entreprise (100 FCFA)** : bouton « 💼 Créer une carte de visite ». Page de création avec **5 modèles** (*Atelier* : papier kraft + tampon artisanal, *Épuré*, *Prestige*, *Wax* : motifs africains, *Aurore*), 6 couleurs, logo, réseau social, et **aperçu en direct recto/verso**. Tant que la carte n'est pas payée, seul un **aperçu filigrané basse définition** est disponible. Le paiement de **100 FCFA** (`BUSINESS_CARD_PRICE` dans `.env`, moyens de paiement selon le pays) débloque le **PNG HD 2100×1200**, le **PDF d'impression** (3,5 × 2 po) et le **.vcf** ; la carte est aussi **envoyée par e-mail** avec le PDF en pièce jointe. Les modifications après paiement sont gratuites. Le QR du verso ajoute le contact dans le téléphone.
- **Reçu par e-mail automatique** : dès que le paiement est validé, le reçu part tout seul. Avec `EMAIL_HOST_USER` + `EMAIL_HOST_PASSWORD` dans `.env`, l'envoi réel (SMTP) s'active automatiquement ; sans identifiants, l'e-mail s'affiche dans la console. Reçus non partis : `python manage.py send_pending_receipts`.

## Mise à jour d'une base existante
Après avoir récupéré cette version : `python manage.py migrate` (champs « ami », cartes de visite, paiement des cartes, suivi d'envoi des reçus).

## Configuration (.env)
Tous les réglages sensibles sont dans le fichier `.env` (modèle : `.env.example`, jamais à partager ni à mettre sur Git).
Principales variables : `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL`, `PLATFORM_COMMISSION_RATE`,
`DB_ENGINE` (sqlite ou postgres), `EMAIL_*` (envoi réel par SMTP), `SOCIAL_FACEBOOK` / `SOCIAL_INSTAGRAM` / `SOCIAL_X`.
Avec `DEBUG=False`, le projet refuse de démarrer tant qu'une vraie `SECRET_KEY` n'est pas définie.

## Le reçu n'arrive pas dans ma boîte mail ?
1. Dans `.env`, `EMAIL_BACKEND=...console.EmailBackend` (valeur par défaut) **n'envoie rien** : l'e-mail s'affiche seulement dans le terminal. Passez au bloc SMTP de `.env.example` (Gmail : mot de passe d'**application**, pas le mot de passe habituel), puis **redémarrez le serveur**.
2. Testez la configuration : `python manage.py send_test_email votre.adresse@gmail.com` (affiche la cause exacte de l'échec).
3. En cas d'échec à l'achat, le paiement et les billets restent valides ; un message l'indique et l'erreur détaillée s'écrit dans le terminal. Le bouton **✉️ Renvoyer le reçu** (page « Mes billets ») renvoie l'e-mail.
4. Vérifiez les courriers indésirables, et gardez `DEFAULT_FROM_EMAIL` identique à `EMAIL_HOST_USER` avec Gmail.

## À brancher en production
- **Paiement réel** : remplacer `charge()` dans `orders/services.py` par FedaPay / KkiaPay / CinetPay.
  En démo, un numéro se terminant par `0000` simule un refus.
- **E-mails réels** : section E-mails du fichier `.env` (voir ci-dessus).
- `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, base PostgreSQL, hébergement des fichiers média.
- Les retraits sont enregistrés « En cours » : le versement réel se fait via l'admin (`/admin/`, créez un superuser) ou une API de paiement sortant.
