from django import forms
from django.core.validators import RegexValidator

from .models import BusinessCard

INPUT = "nt-input"
phone_validator = RegexValidator(r"^[0-9+\-().\s/]{6,30}$", "Numéro de téléphone invalide.")


class BusinessCardForm(forms.ModelForm):
    class Meta:
        model = BusinessCard
        fields = ["theme", "company_name", "contact_name", "job_title", "phone", "email",
                  "website", "address", "tagline", "logo"]
        widgets = {"theme": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].validators.append(phone_validator)
        self.fields["theme"].choices = BusinessCard.Theme.choices
        placeholders = {
            "company_name": "Ex. Atelier Cotonou", "contact_name": "Ex. Awa Adjovi",
            "job_title": "Ex. Directrice", "phone": "+229 01 97 00 00 00",
            "email": "contact@monentreprise.bj", "website": "www.monentreprise.bj",
            "address": "Rue, quartier, ville", "tagline": "Votre slogan en une phrase",
        }
        for name, f in self.fields.items():
            if name in placeholders:
                f.widget.attrs["placeholder"] = placeholders[name]
            if name not in ("theme", "logo"):
                f.widget.attrs.setdefault("class", INPUT)
        self.fields["logo"].widget = forms.FileInput(attrs={"accept": "image/*"})
        self.fields["logo"].help_text = "PNG à fond transparent conseillé. Sans logo, vos initiales sont utilisées."

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "size") and logo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le logo ne doit pas dépasser 5 Mo.")
        return logo
