# NovaTickets · Billetterie en ligne (Django + Tailwind)

Plateforme de billetterie pour le Bénin et l'Afrique de l'Ouest : paiements en FCFA, mobile money, billets nominatifs, reçus e-mail automatiques et cartes de visite d'entreprise.

## 1. Structure

```
novatickets/
├── config/              réglages Django, URLs racine
├── apps/
│   ├── core/            accueil, 210 pays + drapeaux, QR codes, PDF, e-mails, commande seed_demo
│   ├── accounts/        utilisateur unique (rôles spectateur / organisateur), profils
│   ├── events/          événements, types de tickets dynamiques, publication, dashboard organisateur
│   ├── tickets/         commandes, billets, achat (y compris pour un ami), PDF, mes tickets
│   ├── payments/        couche provider (simulation + mobile money), paiements, retraits
│   └── cards/           cartes de visite : éditeur en direct, 100 FCFA, PDF recto/verso
├── templates/           interface Django + Tailwind (partials, e-mails, PDF)
├── static/img/logo.png  ← REMPLACEZ par votre logo NovaTickets (même nom de fichier)
├── tests/test_regles.py tests des règles métier
└── manage.py
```

## 2. Installation

Prérequis : Python 3.11+. Pour les PDF, WeasyPrint a besoin de Pango :
- Debian / Ubuntu : `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`
- macOS : `brew install pango`
- Windows : voir https://doc.courtbouillon.org/weasyprint/stable/first_steps.html

```bash
python -m venv .venv
source .venv/bin/activate              # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                   # puis ajustez les valeurs
python manage.py makemigrations accounts events tickets payments cards core
python manage.py migrate
python manage.py seed_demo             # données de démonstration
python manage.py createsuperuser       # accès /admin/
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000/

> Les migrations ne sont pas livrées : générez-les avec `makemigrations` lors du premier lancement.

## 3. Comptes de démonstration

Mot de passe commun : **`demo12345`**

| Rôle | E-mail | Pays |
|---|---|---|
| Organisateur | orga.vibes@novatickets.demo | Bénin |
| Organisateur | orga.lagune@novatickets.demo | Côte d'Ivoire |
| Organisateur | orga.sahel@novatickets.demo | Burkina Faso |
| Spectateur | aicha.mensah@novatickets.demo | Bénin |
| Spectateur | koffi.hounkpe@novatickets.demo | Bénin |
| Spectateur | fatou.diallo@novatickets.demo | Sénégal |
| Spectateur | yao.kouame@novatickets.demo | Côte d'Ivoire |
| Spectateur | mariam.traore@novatickets.demo | Mali |

`python manage.py seed_demo --reset` repart de zéro.

## 4. Tester le parcours complet

1. Inscrivez-vous en spectateur : choisissez le pays, saisissez le numéro mobile.
2. Ouvrez un événement publié, cliquez « Acheter des billets », cochez « Réserver pour un ami » si besoin.
3. Choisissez un moyen de paiement. Le mode `simulation` valide immédiatement.
4. Le reçu s'affiche dans le terminal (backend console) et les billets apparaissent dans « Mes tickets ».
5. Connectez-vous en organisateur (orga.vibes) : créez un événement, ajoutez des lignes de tickets, publiez, consultez les stats et demandez un retrait.
6. Cartes de visite : créez une carte, puis payez 100 FCFA pour la générer et la télécharger en PDF.

## 5. Règles métier clés

- **Commission** : `NOVATICKETS_COMMISSION_PERCENT` (5 % par défaut). Net organisateur = prix − commission, calculé et stocké sur chaque billet.
- **Achat** : un organisateur ne peut pas acheter pour ses propres événements (contrôle côté serveur).
- **Stock** : réservé dès la création de la commande ; un paiement échoué ne le libère pas.
- **Reçu** : envoyé une seule fois à la validation du paiement, via `confirmer_paiement()` (idempotent).
- **Carte de visite** : aucune génération sans paiement validé.
- **Téléphone** : obligatoire, longueur vérifiée selon le pays, indicatif affiché dynamiquement.

## 6. Brancher une vraie passerelle de paiement

Dans `apps/payments/providers.py` :
1. Créez une classe qui hérite de `ProviderBase` et implémente `initier()` (création de la transaction chez l'agrégateur, par ex. FedaPay ou KkiaPay) et `verifier()`.
2. Ajoutez-la à `PROVIDERS`, puis aux pays dans `MOYENS_PAR_PAYS`.
3. Créez une route webhook qui vérifie la signature puis appelle `confirmer_paiement(paiement)`.
4. Réglez `NOVATICKETS_PAYMENT_PROVIDER` sur votre passerelle et retirez « simulation » du parcours production.

Les appels `ProviderMobileMoney` sont aujourd'hui simulés : chaque point d'appel réseau est marqué `TODO production`.

## 7. E-mails

- Développement : `DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` (le reçu s'affiche dans le terminal).
- Production : SMTP ou un service transactionnel (Brevo, Mailgun…) via `EMAIL_BACKEND` et `DEFAULT_FROM_EMAIL`.

## 8. Logo

Remplacez `static/img/logo.png` par votre fichier (même nom). Il apparaît dans la navbar, les pages d'authentification, les tickets, les e-mails et les PDF. Le fichier fourni est un emplacement provisoire.

## 9. Tests

```bash
python manage.py test tests
```

## 10. Limites connues avant la mise en production

- **OTP** : le modèle exige déjà le téléphone, mais la vérification SMS n'est pas encore branchée.
- **Tailwind** est chargé via CDN pour le développement ; en production, compilez-le avec la CLI Tailwind.
- **Migrations** : à générer avec `makemigrations` avant le premier `migrate`.
- **Retraits** : enregistrés « en cours ». Le versement effectif passe par votre opérateur (à brancher via le provider).
- **Cartes de visite** : livrées en PDF recto/verso (pas d'export image PNG dans cette version).
