from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from .constants import COUNTRY_CHOICES


class SpectateurRegisterForm(UserCreationForm):
    pays = forms.ChoiceField(choices=COUNTRY_CHOICES, initial="Bénin", label="Pays")
    telephone = forms.CharField(label="Téléphone mobile", required=True,
                                 widget=forms.TextInput(attrs={"placeholder": "Ex: 90 00 00 00"}))

    class Meta:
        model = User
        fields = ["username", "email", "nom", "prenoms", "sexe", "pays", "telephone", "profession", "photo"]
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
    pays = forms.ChoiceField(choices=COUNTRY_CHOICES, initial="Bénin", label="Pays")
    telephone = forms.CharField(label="Téléphone mobile", required=True,
                                 widget=forms.TextInput(attrs={"placeholder": "Ex: 90 00 00 00"}))

    class Meta:
        model = User
        fields = ["username", "email", "nom", "prenoms", "sexe", "pays", "telephone", "profession",
                   "nom_structure", "logo_organisateur"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ORGANISATEUR
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    pays = forms.ChoiceField(choices=COUNTRY_CHOICES, label="Pays")

    class Meta:
        model = User
        fields = ["nom", "prenoms", "sexe", "pays", "profession", "photo", "telephone"]
