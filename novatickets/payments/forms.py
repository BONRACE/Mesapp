from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from core.countries import normalize_phone_any

from .methods import payment_methods, payout_methods

INPUT = "nt-input"


class CheckoutForm(forms.Form):
    method = forms.ChoiceField(widget=forms.RadioSelect, label="Moyen de paiement")
    phone = forms.CharField(label="Numéro Mobile Money", max_length=30, required=False)

    def __init__(self, *args, country, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method"].choices = payment_methods(country)
        self.country = country
        self.fields["phone"].widget.attrs.update({"class": INPUT, "inputmode": "tel"})

    def clean(self):
        data = super().clean()
        method = data.get("method")
        if method and method != "card":
            try:
                data["phone"] = normalize_phone_any(data.get("phone", ""), self.country)
            except ValidationError:
                self.add_error("phone", "Saisissez un numéro Mobile Money valide.")
        return data


class WithdrawalForm(forms.Form):
    amount = forms.IntegerField(label="Montant à retirer (FCFA)", min_value=1,
                                widget=forms.NumberInput(attrs={"class": INPUT, "step": 100}))
    method = forms.ChoiceField(label="Moyen de retrait", widget=forms.Select(attrs={"class": INPUT}))
    phone = forms.CharField(label="Numéro / compte de réception", max_length=40,
                            widget=forms.TextInput(attrs={"class": INPUT, "inputmode": "tel"}))

    def __init__(self, *args, user, balance, **kwargs):
        super().__init__(*args, **kwargs)
        self.user, self.balance = user, balance
        self.fields["method"].choices = payout_methods(user.country)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < settings.MIN_WITHDRAWAL:
            raise forms.ValidationError(f"Le retrait minimum est de {settings.MIN_WITHDRAWAL} FCFA.")
        if amount > self.balance:
            raise forms.ValidationError("Montant supérieur à votre solde disponible.")
        return amount

    def clean_phone(self):
        raw = self.cleaned_data["phone"]
        if self.cleaned_data.get("method") == "bank_transfer":
            return raw
        try:
            return normalize_phone_any(raw, self.user.country)
        except ValidationError:
            raise forms.ValidationError("Numéro de réception invalide.")
