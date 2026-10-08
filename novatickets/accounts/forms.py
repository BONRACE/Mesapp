import re

import phonenumbers
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from core.countries import COUNTRY_CHOICES, DEFAULT_COUNTRY, DIAL_BY_CODE

from .models import User


class PhoneMixin:
    """Valide le couple pays + numéro et stocke le numéro au format international."""

    def clean(self):
        data = super().clean()
        code, raw = data.get("country"), (data.get("phone") or "").strip()
        if code and raw:
            dial = str(DIAL_BY_CODE[code])
            digits = re.sub(r"\D", "", raw)
            if raw.startswith("+") and digits.startswith(dial):
                digits = digits[len(dial):]
            full = f"+{dial}{digits}"
            try:
                number = phonenumbers.parse(full)
                valid = phonenumbers.is_possible_number(number)
            except phonenumbers.NumberParseException:
                valid = False
            if valid:
                data["phone"] = full
            else:
                self.add_error("phone", "Numéro de mobile invalide pour le pays choisi.")
        return data


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class BaseRegisterForm(PhoneMixin, forms.ModelForm):
    role = None
    country = forms.ChoiceField(label="Pays", choices=COUNTRY_CHOICES, initial=DEFAULT_COUNTRY, widget=forms.HiddenInput)
    phone = forms.CharField(label="Numéro de mobile", max_length=20, widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "97 00 00 00"}))
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["last_name", "first_name", "sexe", "email", "country"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "email": "E-mail", "sexe": "Sexe"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("last_name", "first_name", "sexe"):
            self.fields[name].required = True
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.Sexe.choices)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail.")
        return email

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        if p2:
            password_validation.validate_password(p2)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.phone = self.cleaned_data["phone"]
        user.role = self.role
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SpectateurRegisterForm(BaseRegisterForm):
    role = User.Role.SPECTATEUR

    class Meta(BaseRegisterForm.Meta):
        fields = ["last_name", "first_name", "sexe", "profession", "photo", "email", "country"]
        labels = {**BaseRegisterForm.Meta.labels, "profession": "Profession", "photo": "Photo (affichée sur votre billet)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profession"].required = True
        self.fields["photo"].required = True


class OrganisateurRegisterForm(BaseRegisterForm):
    role = User.Role.ORGANISATEUR

    class Meta(BaseRegisterForm.Meta):
        fields = ["org_name", "org_logo", "last_name", "first_name", "sexe", "email", "country"]
        labels = {**BaseRegisterForm.Meta.labels, "org_name": "Nom de l'organisation", "org_logo": "Logo de l'organisation"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["org_name"].required = True


class ProfileForm(PhoneMixin, forms.ModelForm):
    country = forms.ChoiceField(label="Pays", choices=COUNTRY_CHOICES, widget=forms.HiddenInput)
    phone = forms.CharField(label="Numéro de mobile", max_length=20, widget=forms.TextInput(attrs={"inputmode": "tel"}))

    class Meta:
        model = User
        fields = ["last_name", "first_name", "sexe", "profession", "photo", "country"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "sexe": "Sexe", "profession": "Profession", "photo": "Photo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance
        if user.is_organizer:
            self.fields["org_name"] = forms.CharField(label="Nom de l'organisation", max_length=150, initial=user.org_name)
            self.fields["org_logo"] = forms.ImageField(label="Logo de l'organisation", required=False)
        self.fields["last_name"].required = True
        self.fields["first_name"].required = True
        self.fields["sexe"].required = True
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.Sexe.choices)
        self.initial["phone"] = user.local_phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = self.cleaned_data["phone"]
        if user.is_organizer:
            user.org_name = self.cleaned_data["org_name"]
            if self.cleaned_data.get("org_logo"):
                user.org_logo = self.cleaned_data["org_logo"]
        if commit:
            user.save()
        return user
