"""Contrôle d'accès par rôle : une seule source de vérité pour les permissions."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Role


def role_requis(*roles):
    """Autorise uniquement les utilisateurs connectés ayant l'un des rôles donnés."""

    def decorateur(vue):
        @login_required
        @wraps(vue)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "Cet espace n'est pas accessible avec votre profil.")
                raise PermissionDenied
            return vue(request, *args, **kwargs)

        return wrapper

    return decorateur


organisateur_requis = role_requis(Role.ORGANISATEUR)
spectateur_requis = role_requis(Role.SPECTATEUR, Role.ORGANISATEUR)
