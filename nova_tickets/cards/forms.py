from django import forms

from payments.models import Transaction

from .models import BusinessCard


class BusinessCardForm(forms.ModelForm):
    website = forms.URLField(label="Site web", required=False, assume_scheme="https")
    linkedin = forms.URLField(label="LinkedIn", required=False, assume_scheme="https")

    class Meta:
        model = BusinessCard
        fields = ["full_name", "job_title", "company", "phone", "email", "website", "linkedin", "city", "bio", "theme", "layout", "show_on_ticket"]
        widgets = {
            "theme": forms.RadioSelect,
            "layout": forms.RadioSelect,
            "phone": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+229 01 97 00 00 01"}),
            "bio": forms.TextInput(attrs={"placeholder": "Ex : Développeur web — je construis des produits pour l'Afrique de l'Ouest"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["layout"].required = False           # absent d'un ancien formulaire : on garde le style actuel
        self.fields["theme"].choices = list(BusinessCard.Theme.choices)   # pas de choix vide « ---- »
        self.fields["layout"].choices = list(BusinessCard.Layout.choices)

    def clean_layout(self):
        return self.cleaned_data.get("layout") or self.instance.layout or BusinessCard.Layout.CLASSIC

    def clean_linkedin(self):
        url = self.cleaned_data.get("linkedin", "")
        if url and "linkedin.com" not in url.lower():
            raise forms.ValidationError("Indiquez une adresse LinkedIn (linkedin.com/…).")
        return url


class ActivationForm(forms.Form):
    """Paiement Mobile Money de l'activation de la carte."""
    provider = forms.ChoiceField(label="Opérateur", choices=[c for c in Transaction.Provider.choices if c[0] != "FEDA"], widget=forms.RadioSelect, required=False)
    phone = forms.CharField(label="Numéro Mobile Money", max_length=20,
                            widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "01 97 00 00 01"}), required=False)

    def clean(self):
        data = super().clean()
        from payments import fedapay
        if not fedapay.enabled() and not (data.get("provider") and data.get("phone")):
            raise forms.ValidationError("Choisissez un opérateur et saisissez votre numéro Mobile Money.")
        return data
