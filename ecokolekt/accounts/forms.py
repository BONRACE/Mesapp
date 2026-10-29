import re

from django import forms

from .models import Role, User

PHONE_RE = re.compile(r"\+\d{8,15}")


class PhoneForm(forms.Form):
    phone_number = forms.CharField(
        label="Numéro de téléphone",
        max_length=25,
        widget=forms.TextInput(attrs={
            "placeholder": "+229 97 00 00 00",
            "inputmode": "tel",
            "autocomplete": "tel",
        }),
    )

    def clean_phone_number(self):
        raw = re.sub(r"[\s\-.]", "", self.cleaned_data["phone_number"])
        if not PHONE_RE.fullmatch(raw):
            raise forms.ValidationError("Format attendu : +229 suivi de votre numéro.")
        return raw


class OTPForm(forms.Form):
    code = forms.CharField(
        label="Code reçu par SMS",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "placeholder": "••••••",
        }),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Le code ne contient que des chiffres.")
        return code


class OnboardingForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Votre profil",
        choices=Role.choices,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = User
        fields = ["role", "full_name", "organization", "district"]
        labels = {
            "full_name": "Nom complet",
            "organization": "Structure (facultatif)",
            "district": "Quartier / commune",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Ex. Aïcha Houngbo"}),
            "organization": forms.TextInput(attrs={"placeholder": "Ex. Coopérative Ouidah"}),
            "district": forms.TextInput(attrs={"placeholder": "Ex. Cadjehoun, Cotonou"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_onboarded = True
        if commit:
            user.save()
        return user
