"""Connexion à l'administration Django protégée par le même anti brute-force que la page de connexion publique."""
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm

from . import throttle


class ThrottledAdminAuthenticationForm(AdminAuthenticationForm):
    def clean(self):
        ident = self.cleaned_data.get("username", "") or ""
        if throttle.is_locked(self.request, ident):
            raise forms.ValidationError("Trop de tentatives. Réessayez dans quelques minutes.", code="locked")
        try:
            data = super().clean()
        except forms.ValidationError:
            throttle.register_failure(self.request, ident)
            raise
        throttle.reset(self.request, ident)
        return data
