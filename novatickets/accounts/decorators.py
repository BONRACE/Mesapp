from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def organizer_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_organizer:
            messages.error(request, "Cet espace est réservé aux organisateurs.")
            return redirect("orders:my_space")
        return view(request, *args, **kwargs)

    return wrapper
