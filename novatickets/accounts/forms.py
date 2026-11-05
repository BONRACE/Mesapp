import re

import phonenumbers
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from core.validators import harden_image_fields
from core.countries import COUNTRIES, COUNTRY_CHOICES, DEFAULT_COUNTRY, DIAL_BY_CODE

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
    username = forms.CharField(label="E-mail ou nom d'utilisateur", widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)

    def clean_username(self):
        return self.cleaned_data["username"].strip()

    def clean(self):
        from . import throttle
        ident = self.cleaned_data.get("username", "")
        if throttle.is_locked(self.request, ident):
            raise forms.ValidationError("Trop de tentatives de connexion. Réessayez dans quelques minutes ou réinitialisez votre mot de passe.", code="locked")
        try:
            data = super().clean()
        except forms.ValidationError:
            throttle.register_failure(self.request, ident)
            raise
        throttle.reset(self.request, ident)
        return data


def flag_emoji(code):
    """BJ -> 🇧🇯 (deux lettres régionales Unicode)."""
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper())


REGISTER_COUNTRY_CHOICES = [(c["code"], f"{flag_emoji(c['code'])} {c['name']} (+{c['dial']})") for c in COUNTRIES]


class BaseRegisterForm(PhoneMixin, forms.ModelForm):
    role = None
    country = forms.ChoiceField(label="Pays", choices=REGISTER_COUNTRY_CHOICES, initial=DEFAULT_COUNTRY)
    phone = forms.CharField(label="Numéro de mobile", max_length=20, widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "97 00 00 00"}))
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["last_name", "first_name", "sexe", "email", "username", "country"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "email": "E-mail", "sexe": "Sexe", "username": "Nom d'utilisateur"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("last_name", "first_name", "sexe"):
            self.fields[name].required = True
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.Sexe.choices)
        harden_image_fields(self, "photo", "org_logo")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        if User.objects.filter(email__iexact=username).exists():
            raise forms.ValidationError("Choisissez un autre nom d'utilisateur.")     # évite toute confusion avec l'e-mail d'un autre compte
        return username

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
            d = self.cleaned_data       # le validateur de similarité compare le mot de passe au nom, à l'e-mail et à l'identifiant
            password_validation.validate_password(p2, User(username=d.get("username", ""), email=d.get("email", ""),
                                                           first_name=d.get("first_name", ""), last_name=d.get("last_name", "")))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = self.cleaned_data["phone"]
        user.role = self.role
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SpectateurRegisterForm(BaseRegisterForm):
    role = User.Role.SPECTATEUR

    class Meta(BaseRegisterForm.Meta):
        fields = ["last_name", "first_name", "sexe", "profession", "photo", "email", "username", "country"]
        labels = {**BaseRegisterForm.Meta.labels, "profession": "Profession", "photo": "Photo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profession"].required = False      # facultative (cf. maquette)
        self.fields["photo"].required = True
        self.fields["photo"].help_text = "Elle apparaîtra sur votre billet."


class OrganisateurRegisterForm(BaseRegisterForm):
    role = User.Role.ORGANISATEUR

    class Meta(BaseRegisterForm.Meta):
        fields = ["org_name", "org_logo", "last_name", "first_name", "sexe", "email", "username", "country"]
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
            self.fields["signature_mode"] = forms.ChoiceField(
                label="Signature sur les reçus et billets", choices=User.SignatureMode.choices, widget=forms.RadioSelect,
                initial=user.signature_mode)
            self.fields["signature"] = forms.CharField(
                label="Nom et fonction du manager", max_length=120, required=False, initial=user.signature,
                help_text="Ex : Adama Touré – Directeur. Utilisé avec « Signature avec le nom du manager ».")
            self.fields["signature_image"] = forms.ImageField(label="Importer une signature (image)", required=False)
            self.fields["signature_drawn"] = forms.CharField(required=False, widget=forms.HiddenInput)
        harden_image_fields(self, "photo", "org_logo", "signature_image")
        self.fields["last_name"].required = True
        self.fields["first_name"].required = True
        self.fields["sexe"].required = True
        self.fields["sexe"].choices = [("", "Choisir…")] + list(User.Sexe.choices)
        self.initial["phone"] = user.local_phone

    def clean(self):
        data = super().clean()
        if not self.instance.is_organizer:
            return data
        png = None
        drawn = (data.get("signature_drawn") or "").strip()
        if drawn:                                         # tracé à l'écran : data URL PNG envoyée par le canvas
            png = _signature_from_bytes(self, _decode_data_url(drawn))
        elif data.get("signature_image"):
            png = _signature_from_bytes(self, data["signature_image"].read())
        data["_signature_png"] = png
        mode = data.get("signature_mode")
        if mode == User.SignatureMode.IMAGE and not png and not self.instance.signature_image:
            self.add_error("signature_image", "Dessinez ou importez votre signature.")
        if mode == User.SignatureMode.MANAGER and not (data.get("signature") or "").strip():
            self.add_error("signature", "Saisissez le nom du manager.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = self.cleaned_data["phone"]
        if user.is_organizer:
            user.org_name = self.cleaned_data["org_name"]
            user.signature = self.cleaned_data.get("signature", "")
            user.signature_mode = self.cleaned_data.get("signature_mode") or user.signature_mode
            png = self.cleaned_data.get("_signature_png")
            if png:
                from django.core.files.base import ContentFile
                if user.signature_image:
                    user.signature_image.delete(save=False)
                user.signature_image.save(f"signature-{user.pk}.png", ContentFile(png), save=False)
            if self.cleaned_data.get("org_logo"):
                user.org_logo = self.cleaned_data["org_logo"]
        if commit:
            user.save()
        return user


def _decode_data_url(value):
    import base64
    try:
        return base64.b64decode(value.split(",", 1)[1], validate=False)
    except Exception:
        return b""


def _signature_from_bytes(form, raw):
    """Valide l'image (taille, format) et la normalise en PNG ≤ 600×200. None + erreur de champ si illisible."""
    import io

    from PIL import Image
    if not raw or len(raw) > 2 * 1024 * 1024:
        form.add_error("signature_image", "Signature illisible ou trop lourde (2 Mo maximum).")
        return None
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGBA")
            im.thumbnail((600, 200))
            out = io.BytesIO()
            im.save(out, "PNG", optimize=True)
            return out.getvalue()
    except Exception:
        form.add_error("signature_image", "Image de signature invalide.")
        return None
