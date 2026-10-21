from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

from core.countries import country_choices, normalize_phone

User = get_user_model()

INPUT = "nt-input"


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Adresse e-mail", widget=forms.EmailInput(attrs={"autofocus": True, "class": INPUT}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"class": INPUT}))
    error_messages = {
        "invalid_login": "E-mail ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }


class _PhoneCountryMixin:
    """Valide le téléphone mobile en fonction du pays choisi (stocké en E.164)."""

    def clean(self):
        data = super().clean()
        country, phone = data.get("country"), data.get("phone")
        if country and phone:
            try:
                data["phone"] = normalize_phone(phone, country)
            except forms.ValidationError as exc:
                self.add_error("phone", exc)
        return data


class RegisterForm(_PhoneCountryMixin, forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)
    country = forms.ChoiceField(label="Pays", choices=country_choices, initial="BJ")

    class Meta:
        model = User
        fields = [
            "last_name", "first_name", "email", "country", "phone",
            "sexe", "profession", "photo", "organisation_name", "organisation_logo",
        ]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "phone": "Téléphone mobile"}

    def __init__(self, *args, role="spectateur", **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        for name in ("last_name", "first_name", "phone"):
            self.fields[name].required = True
        if role == "spectateur":
            for name in ("sexe", "profession", "photo"):
                self.fields[name].required = True
            del self.fields["organisation_name"], self.fields["organisation_logo"]
        else:
            self.fields["organisation_name"].required = True
            self.fields["photo"].label = "Photo (facultative)"
        self.fields["sexe"].choices = [("", "— Choisir —")] + list(User.Sexe.choices)
        self.fields["phone"].widget.attrs.update(
            {"inputmode": "tel", "placeholder": "Numéro mobile", "autocomplete": "tel-national"}
        )
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.FileInput, forms.ClearableFileInput)):
                field.widget.attrs.setdefault("class", INPUT)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
        return photo

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.role = self.role
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(_PhoneCountryMixin, forms.ModelForm):
    country = forms.ChoiceField(label="Pays", choices=country_choices)

    class Meta:
        model = User
        fields = ["last_name", "first_name", "country", "phone", "sexe", "profession", "photo",
                  "organisation_name", "organisation_logo"]
        labels = {"last_name": "Nom", "first_name": "Prénoms", "phone": "Téléphone mobile"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.is_organisateur:
            del self.fields["organisation_name"], self.fields["organisation_logo"]
        else:
            self.fields["organisation_name"].required = True
        self.fields["sexe"].choices = [("", "— Choisir —")] + list(User.Sexe.choices)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.FileInput, forms.ClearableFileInput)):
                field.widget.attrs.setdefault("class", INPUT)
