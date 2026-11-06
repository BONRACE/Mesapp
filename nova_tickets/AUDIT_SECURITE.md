# Audit de sécurité — NovaTickets (Django)

Audit du code source avant déploiement. Chaque point a été **vérifié dans le code** ; les failles trouvées ont été **corrigées** et couvertes par
des tests (`core/tests_security.py`, 49 tests, + 157 tests fonctionnels existants). Lancer : `python manage.py test`.

## Synthèse

| # | Gravité | Constat | État |
|---|---|---|---|
| 1 | Moyenne | `orders:ticket_qr` : le QR (lien **signé** de vérification) était servi à n'importe qui connaissant la référence du billet | **Corrigé** — porteur ou organisateur de l'événement connectés uniquement |
| 2 | Moyenne | Pages `payments:status`, `statut.json`, `recu.pdf` accessibles à quiconque possède l'UUID (e-mail du payeur dans le reçu) | **Corrigé** — propriétaire connecté pour toute transaction liée à une commande / carte / abonnement |
| 3 | Moyenne | Connexion à `/admin/` sans anti brute-force (seule la page publique était protégée) | **Corrigé** — `ThrottledAdminAuthenticationForm` |
| 4 | Moyenne | Webhook : en production, un statut SUCCESS **sans montant** était accepté (signature valide requise) | **Corrigé** — montant obligatoire quand `MOMO_GATEWAY_MODE=live` |
| 5 | Faible | Aucune politique de contenu (CSP) : une XSS éventuelle aurait pu charger des scripts / envoyer des formulaires ailleurs | **Corrigé** — CSP + `frame-ancestors 'none'`, `object-src 'none'`, `form-action 'self'` (vérifiée sans violation sur toutes les pages) |
| 6 | Faible | `check --deploy` : avertissement HSTS preload | **Voulu** (irréversible), documenté ; reste un test qui exige 0 avertissement |
| 7 | À faire | Compteurs anti brute-force en mémoire de processus (`LocMemCache`) | **Prod : Redis/Memcached** (voir §4) |
| 8 | À faire | Paiements Orange / Wave / carte / PayPal / virement encore **simulés** | Interdits en prod par `ALLOW_SIMULATED_PAYMENTS=False` (le démarrage refuse sinon) ; brancher une vraie passerelle |
| 9 | À faire | SQLite, pas de sauvegarde, pas de 2FA admin, dépendances non épinglées | Voir la checklist de déploiement |

Déjà en place avant cet audit (revérifié) : références de billets aléatoires (`secrets`, 10 caractères → pas d'ID séquentiel exposé), lien QR signé
HMAC, validation atomique du scan, montants calculés côté serveur, webhook HMAC-SHA256 + idempotence + contrôle du montant + horodatage, garde-fou de
démarrage en production, cookies `HttpOnly` / `SameSite` / `Secure`, HSTS, mots de passe validés, upload d'images validé.

---

## 1. Authentification, sessions, rôles

### Scénarios d'attaque
- **Brute-force / credential stuffing** sur `/compte/connexion/` ou `/admin/` : milliers d'essais par minute.
- **Énumération de comptes** : différencier « e-mail inconnu » de « mauvais mot de passe » (message ou temps de réponse).
- **Détournement du lien de réinitialisation** par en-tête `Host` falsifié ; bombardement d'e-mails ; réutilisation d'un lien.
- **Fixation / vol de session**, session qui survit à un changement de mot de passe.
- **Élévation de privilèges** : un spectateur appelle des URL organisateur ; inscription avec `role=organisateur`, `is_staff=on` dans le POST.
- **Open redirect** via `?next=https://evil`.

### Checklist (où regarder)
| Point | Fichier | Constat |
|---|---|---|
| Verrou après N échecs (IP + identifiant) et plafond par IP | `accounts/throttle.py`, `accounts/forms.py::LoginForm.clean` | OK ; **ajouté** pour l'admin : `accounts/admin_login.py` |
| IP réelle derrière un proxy | `throttle.client_ip` | OK : `X-Forwarded-For` lu seulement si `BEHIND_PROXY=True` (sinon falsifiable) |
| Temps constant / pas d'énumération | `accounts/backends.py` | OK (`User().set_password()` quand l'utilisateur n'existe pas) |
| Réinitialisation : limite 5/h, réponse identique, lien 1 h à usage unique | `accounts/views.py::ThrottledPasswordResetView`, `PASSWORD_RESET_TIMEOUT` | OK (jeton lié au hash du mot de passe : usage unique) |
| Poisoning du `Host` | `ALLOWED_HOSTS` | OK : le démarrage refuse `*` et la liste vide en production |
| Cookies | `settings.py` | `SESSION_COOKIE_HTTPONLY`, `SAMESITE=Lax`, `SECURE` si `DEBUG=False`, session 7 jours |
| Session après changement de mot de passe / suppression de compte | modèle `AbstractBaseUser` (hash dans la session) | OK, testé |
| RBAC | `accounts/decorators.py::organizer_required` | OK : toutes les vues `/organisateur/*`, scanner, analytics, retraits, abonnement |
| Mass assignment à l'inscription | `accounts/forms.py` (`fields = [...]`, `user.role = self.role`) | OK : le rôle vient de l'URL, jamais du POST ; `is_staff` non exposé |
| Open redirect | `LoginView.get_redirect_url` | OK (hôte vérifié par Django), testé |
| CSRF | `CsrfViewMiddleware` | OK ; aucune vue `csrf_exempt` sauf le webhook (signé) |

### Correctifs / bonnes pratiques
```python
# Vue réservée à un rôle (déjà en place) — accounts/decorators.py
def organizer_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *a, **kw):
        if not request.user.is_organizer:
            messages.error(request, "Espace réservé aux organisateurs.")
            return redirect("orders:my_space")
        return view(request, *a, **kw)
    return wrapper

# Équivalent en vue basée sur classe
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
class OrganizerOnly(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_organizer

# Anti brute-force de l'admin (ajouté) — config/urls.py
from accounts.admin_login import ThrottledAdminAuthenticationForm
admin.site.login_form = ThrottledAdminAuthenticationForm
```
Recommandé en plus : URL d'admin non devinable (`ADMIN_URL=gestion-x7k2/`), 2FA admin (`django-otp`), vérification de l'e-mail à l'inscription.

---

## 2. Billetterie, QR codes, scanner

### Scénarios d'attaque
- **Falsification** : fabriquer un QR pour une référence devinée ; **énumération** `/verification/TK-…` ; **ID auto-incrémentés** (`/billets/1/`, `/billets/2/`…).
- **Duplication** : photographier un QR et le scanner deux fois ; **course critique** : deux téléphones scannent le même billet à la même milliseconde.
- **IDOR** : un organisateur B scanne / consulte les billets, ventes ou statistiques de l'organisateur A ; un acheteur ouvre le billet d'un autre.
- **Fuite du lien signé** : récupérer l'image du QR d'un billet d'autrui.

### Checklist
| Point | Fichier | Constat |
|---|---|---|
| Références aléatoires, non séquentielles | `orders/services.py::make_reference` (`secrets.choice`) | OK : `TK-` + 10 caractères (≈ 2⁵⁰), jamais l'`id` en URL |
| QR = lien signé HMAC (`?s=`) | `orders/services.py::ticket_signature`, `core/views.py::verify` | OK : lien non signé ou inconnu → même 404 |
| Scan atomique | `scanner/services.py::check_in` | OK : `transaction.atomic` + `select_for_update` + `UPDATE … WHERE used_at IS NULL` (un seul gagnant même sous SQLite) |
| Billet d'un autre organisateur | `check_in` | OK : traité « invalide », sans fuite d'information |
| Filtrage par propriétaire | `events/views.py`, `scanner/views.py`, `analytics/views.py`, `payouts/views.py` : `get_object_or_404(..., organizer=request.user)` | OK |
| Billets / reçus / commandes de l'acheteur | `orders/views.py` (`buyer=request.user`) | OK (404, pas 403 : n'avoue pas l'existence) |
| **Image du QR** | `orders/views.py::ticket_qr` | **Corrigé** (voir ci-dessous) |
| Photocopie d'un QR valide | — | **Limite physique** : le 1er scan gagne, les suivants sont « déjà utilisé » ; contrôler l'identité (nom + photo affichés au scanner) |

### Correctifs
```python
# orders/views.py — le QR contient le lien signé : réservé au porteur et à l'organisateur
@login_required
def ticket_qr(request, reference):
    ticket = get_object_or_404(Ticket.objects.select_related("order__event"), reference=reference)
    if request.user.id not in (ticket.order.buyer_id, ticket.order.event.organizer_id):
        raise Http404
    resp = HttpResponse(qr_png(verify_url(ticket)), content_type="image/png")
    resp["Cache-Control"] = "private, no-store"
    return resp

# scanner/services.py — validation sans course critique
with transaction.atomic():
    ticket = Ticket.objects.select_for_update(of=("self",)).filter(reference=ref, order__status="paid").first()
    updated = Ticket.objects.filter(pk=ticket.pk, used_at__isnull=True).update(used_at=timezone.now())
    # updated == 1 -> valide ; 0 -> quelqu'un a scanné entre-temps : « déjà utilisé »
```
Option « anti-capture » : QR rotatif (jeton TOTP renouvelé toutes les 30 s dans la page du billet) si la fraude par capture devient un sujet.

---

## 3. Paiement et transactions

### Scénarios d'attaque
- **Prix modifié côté navigateur** (`price=1`, `total=1`, autre `ticket_type` d'un autre événement, quantité négative / énorme).
- **Webhook falsifié** : POST sur `/paiement/webhook/` avec `status=APPROVED` pour obtenir des billets gratuits.
- **Rejeu** : renvoyer un vieux webhook valide ; notification contradictoire tardive (FAILED après SUCCESS).
- **Montant altéré** dans un webhook valide ; **double paiement** ; **course** entre deux webhooks.
- **Paiement « simulé »** laissé actif en production = billets gratuits.
- **Achat de ses propres billets** pour fabriquer des ventes fictives ; payer la commande d'un autre.

### Checklist
| Point | Fichier | Constat |
|---|---|---|
| Montant jamais lu dans le POST | `orders/views.py::checkout` → `orders/services.py::create_order` (`ticket_type.price * quantity`) | OK, testé (`price=1` ignoré) |
| `ticket_type` rattaché à l'événement de l'URL | `get_object_or_404(TicketType, pk=…, event_id=pk)` | OK |
| Quantité bornée | `MAX_PER_ORDER`, stock vérifié, revérifié au paiement sous verrou | OK ; stock épuisé entre-temps → « À rembourser » |
| Signature webhook | `payments/services.py::signature_is_valid` (`hmac.compare_digest`) | OK ; secret refusé s'il est par défaut en prod |
| Idempotence / verrou | `apply_gateway_status` (`select_for_update`, état final jamais modifié) | OK, testé |
| Contrôle du montant | `apply_gateway_status` | OK ; **corrigé** : montant **obligatoire** en mode `live` |
| Anti-rejeu temporel | `payments/views.py::webhook` (`MOMO_WEBHOOK_MAX_AGE`, champ `timestamp`) | OK si le fournisseur envoie un horodatage ; sinon l'idempotence suffit |
| Livraison atomique | `fulfil` dans le même `atomic` que le changement de statut | OK : si l'activation échoue, le statut est annulé, la passerelle renverra |
| Paiements simulés | `ALLOW_SIMULATED_PAYMENTS`, garde-fou au démarrage | OK |
| Page de suivi / reçu | `payments/views.py` | **Corrigé** : propriétaire connecté (404 sinon) |
| Organisateur achète son événement / paie la commande d'autrui | `create_order`, `pay` (`buyer=request.user`) | OK, testé |

### Correctifs
```python
# payments/services.py — traitement idempotent et atomique d'une notification
with transaction.atomic():
    tx = Transaction.objects.select_for_update().get(reference=reference)
    if not tx.is_pending:
        return tx, False                       # rejeu / doublon : aucun effet
    if new_status == SUCCESS and amount is None and settings.MOMO_GATEWAY_MODE == "live":
        raise PaymentError("Montant absent de la notification.")
    if amount is not None and Decimal(str(amount)) != tx.amount:
        raise PaymentError("Montant incohérent.")
    tx.status = new_status; tx.save()
    if new_status == SUCCESS:
        fulfil(tx)                             # même transaction SQL

# payments/views.py — accès à une transaction liée : propriétaire seulement
def _owner_or_404(request, tx):
    owner_id = (tx.order.buyer_id if tx.order_id else tx.business_card.user_id if tx.business_card_id
                else tx.subscription.user_id if tx.subscription_id else None)
    if owner_id is not None and (not request.user.is_authenticated or request.user.id != owner_id):
        raise Http404
```
En production : restreindre l'IP source du webhook côté nginx (liste d'adresses de l'agrégateur), limiter le débit (`limit_req`) sur `/paiement/webhook/`, `/compte/connexion/` et `/evenements/*/acheter/`.

---

## 4. Vulnérabilités Django et configuration

### Scénarios d'attaque
- **XSS stockée** : nom d'événement, bio de carte, nom/prénom injectant `<script>` (page, e-mail, **PDF** reportlab avec balises `<b>`, `<para>`).
- **Injection SQL** : champ de recherche, `?event=1 OR 1=1`, références de scan.
- **Upload malveillant** : « image » PHP/SVG avec script, bombe de décompression (image géante).
- **SSRF** : faire appeler à l'application une URL interne (images distantes, webhooks sortants).
- **Configuration** : `DEBUG=True` en production (traces + variables), `SECRET_KEY` par défaut (cookies, jetons et signatures de QR forgeables), `ALLOWED_HOSTS=*`, HTTP sans HTTPS, cookies sans `Secure`.
- **Clickjacking**, MIME sniffing, fuite du `Referer`.

### Checklist
| Point | Constat |
|---|---|
| ORM uniquement, aucun `.raw()`, `.extra()`, `cursor()` | OK (recherche `grep -rn "\.raw(\|\.extra(\|cursor()"` : 0 résultat) |
| Auto-échappement des gabarits, pas de `\|safe` / `mark_safe` | OK (testé : `<script>` du nom d'événement / de la carte échappé) |
| PDF | OK : texte dessiné avec `drawString`, pas de `Paragraph` à balises ; testé avec noms contenant du balisage |
| Liens saisis par l'utilisateur (`website`, `linkedin`) | OK : `URLField` (http/https seulement → pas de `javascript:`) |
| Upload | `core/validators.py` : taille (3 Mo), dimensions (6000 px), Pillow ; testé : faux PNG (PHP) et SVG refusés. Les `/media/` ne sont **pas** servis par Django hors `DEBUG` (à servir par nginx sans exécution de scripts) |
| SSRF | Aucun téléchargement d'URL fournie par un utilisateur ; seul appel sortant : `MOMO_API_BASE_URL` (fixé par l'administrateur, **https obligatoire** en production, vérifié au démarrage) |
| Clickjacking / sniffing / Referer | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy`, `COOP`, **CSP ajoutée** |
| Pages privées | `Cache-Control: private, no-store` pour tout utilisateur connecté |
| `settings.py` en production | `config/settings.py` **refuse de démarrer** si : `SECRET_KEY` < 40 car. ou par défaut, `ALLOWED_HOSTS` vide ou `*`, `MOMO_WEBHOOK_SECRET` par défaut, `SITE_URL` non https, paiements simulés actifs. `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, HSTS 1 an : actifs dès `DEBUG=False` |
| `manage.py check --deploy` | 0 avertissement avec la configuration de production (testé) |

### `.env` de production (exemple)
```ini
DEBUG=False
SECRET_KEY=<python -c "import secrets;print(secrets.token_urlsafe(64))">
ALLOWED_HOSTS=novatickets.app,www.novatickets.app
CSRF_TRUSTED_ORIGINS=https://novatickets.app
SITE_URL=https://novatickets.app
BEHIND_PROXY=True                  # nginx / Render / Railway termine le HTTPS
ADMIN_URL=gestion-x7k2/
MOMO_GATEWAY_MODE=live
MOMO_API_BASE_URL=https://…        # https obligatoire
MOMO_API_KEY=…
MOMO_WEBHOOK_SECRET=<secret long aléatoire>
ALLOW_SIMULATED_PAYMENTS=False
```
Cache partagé (obligatoire avec plusieurs workers, sinon chaque worker a son propre compteur anti brute-force) :
```python
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://127.0.0.1:6379/1"}}
```

---

## Checklist de déploiement

1. `DEBUG=False` + `.env` ci-dessus ; `python manage.py check --deploy` sans avertissement.
2. HTTPS (Let's Encrypt) ; nginx : `limit_req` sur connexion / webhook / achat, taille max de corps (`client_max_body_size 8m`), `/media/` servi en lecture seule sans exécution.
3. Base **PostgreSQL** (au lieu de SQLite), sauvegardes chiffrées quotidiennes testées.
4. Redis pour le cache (anti brute-force) ; sessions en base (par défaut).
5. `pip install pip-audit && pip-audit` à chaque mise à jour ; épingler les versions (`pip freeze > requirements.lock`).
6. Journaux : surveiller « Webhook refusé », « Montant incohérent », « DOUBLE PAIEMENT », « Trop de tentatives ».
7. Brancher la vraie passerelle ; `ALLOW_SIMULATED_PAYMENTS=False`.
8. Compte administrateur avec mot de passe fort + 2FA ; ne jamais publier `.env`.
9. Test d'intrusion externe avant l'ouverture au public (cet audit est un audit de code, pas un test d'intrusion en conditions réelles).
