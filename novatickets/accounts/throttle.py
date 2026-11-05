"""Anti brute-force : compteur d'échecs par (IP + identifiant) et par IP, stocké dans le cache Django.

- après LOGIN_MAX_ATTEMPTS échecs sur le même compte depuis la même IP -> verrou LOGIN_LOCK_SECONDS ;
- plafond global par IP (10 × plus large) contre le « credential stuffing » (un mot de passe, mille comptes) ;
- un succès remet à zéro le compteur du couple IP + identifiant.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    """IP du client. X-Forwarded-For n'est lu que derrière un proxy de confiance (BEHIND_PROXY), dernière valeur = celle du proxy."""
    if getattr(settings, "BEHIND_PROXY", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _key(kind, *parts):
    raw = "|".join(p.strip().lower() for p in parts)
    return f"throttle:{kind}:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _limits():
    per_account = settings.LOGIN_MAX_ATTEMPTS
    return per_account, per_account * 10, settings.LOGIN_LOCK_SECONDS


def is_locked(request, identifier):
    per_account, per_ip, _ = _limits()
    ip = client_ip(request)
    return (cache.get(_key("acct", ip, identifier), 0) >= per_account) or (cache.get(_key("ip", ip), 0) >= per_ip)


def register_failure(request, identifier):
    _, _, window = _limits()
    ip = client_ip(request)
    for key in (_key("acct", ip, identifier), _key("ip", ip)):
        cache.add(key, 0, window)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, window)


def reset(request, identifier):
    cache.delete(_key("acct", client_ip(request), identifier))


def hit_hourly(request, scope, identifier="", limit=None):
    """Compteur d'actions par heure (ex. demandes de réinitialisation). Renvoie True si la limite est dépassée."""
    limit = limit or settings.RESET_MAX_PER_HOUR
    key = _key(scope, client_ip(request), identifier)
    cache.add(key, 0, 3600)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)
        count = 1
    return count > limit
