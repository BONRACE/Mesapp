"""Décorateurs de contrôle d'accès par rôle."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(role):
    """Exige un utilisateur connecté ayant le rôle donné ; sinon 403."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied("Cette page est réservée à un autre type de compte.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


organisateur_required = role_required("organisateur")
spectateur_required = role_required("spectateur")
