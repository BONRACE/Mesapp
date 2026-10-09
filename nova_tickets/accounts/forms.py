import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from core.countries import all_countries, country_choices, get_country

from .models import User

INPUT = "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-base focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 outline-none"


def _style(form):
    for name, f in form.fields.items():
        w = f.widget
        if isinstance(w, forms.CheckboxInput):
            continue
        if isinstance(w, forms.FileInput):
            w.attrs.setdefault("class", "block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-4 file:py-2.5 file:text-emerald-700 file:font-medium")
            w.attrs.setdefault("accept", "image/*")
        else:
            w.attrs.setdefault("class", INPUT)


class PhoneMixin:
    """Ajoute l'indicatif du pays choisi devant le numéro (obligatoire)."""

    def clean_phone(self):
        raw = self.cleaned_data.get("phone", "")
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 6 or len(digits) > 15:
            raise ValidationError("Entrez un numéro de téléphone mobile valide.")
        return digits

    def _full_phone(self):
        country = get_country(self.cleaned_data.get("country", "BJ"))
        dial = country["dial"] if country else ""
        return f"{dial} {self.cleaned_data['phone']}".strip()


class LoginForm(AuthenticationForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["username"].label = "Nom d'utilisateur"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})
        self.fields["password"].label = "Mot de passe"
        _style(self)


class RegisterForm(PhoneMixin, forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    country = forms.ChoiceField(label="Pays", choices=country_choices, initial="BJ")
    phone = forms.CharField(label="Téléphone mobile", widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "97 00 00 00"}))

    class Meta:
        model = User
        fields = ["last_name", "first_name", "username", "email", "sexe", "profession", "country", "phone", "photo", "org_name", "org_logo"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "username": "Nom d'utilisateur", "email": "E-mail", "sexe": "Sexe", "profession": "Profession", "photo": "Photo"}

    def __init__(self, *args, role=User.SPECTATEUR, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        for f in ("last_name", "first_name", "email", "sexe"):
            self.fields[f].required = True
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.SEXES)
        if role == User.ORGANISATEUR:
            self.fields["org_name"].required = True
            self.fields["org_name"].label = "Nom de l'organisation"
            self.fields["org_logo"].label = "Logo de l'organisation"
            self.fields["photo"].required = False
        else:
            del self.fields["org_name"]
            del self.fields["org_logo"]
            self.fields["photo"].required = True
            self.fields["photo"].help_text = "Elle apparaîtra sur votre billet."
        _style(self)

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.role
        user.phone = self._full_phone()
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(PhoneMixin, forms.ModelForm):
    country = forms.ChoiceField(label="Pays", choices=country_choices)
    phone = forms.CharField(label="Téléphone mobile", widget=forms.TextInput(attrs={"inputmode": "tel"}))

    class Meta:
        model = User
        fields = ["last_name", "first_name", "email", "sexe", "profession", "country", "phone", "photo", "org_name", "org_logo"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "email": "E-mail", "sexe": "Sexe", "profession": "Profession", "photo": "Photo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance
        # n'affiche que le numéro national dans le champ
        if user.phone:
            dial = (get_country(user.country) or {}).get("dial", "")
            self.initial["phone"] = user.phone.replace(dial, "", 1).strip()
        if not user.is_organisateur:
            self.fields.pop("org_name")
            self.fields.pop("org_logo")
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.SEXES)
        _style(self)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = self._full_phone()
        if commit:
            user.save()
        return user
