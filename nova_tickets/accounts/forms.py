from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class SpectateurRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email", "nom", "prenoms", "sexe", "profession", "photo"]
        widgets = {
            "sexe": forms.Select(attrs={"class": "input-glass"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.SPECTATEUR
        if commit:
            user.save()
        return user


class OrganisateurRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email", "nom", "prenoms", "sexe", "profession",
                   "nom_structure", "logo_organisateur"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ORGANISATEUR
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["nom", "prenoms", "sexe", "profession", "photo", "telephone"]
