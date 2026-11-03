from django import forms

from .models import Transaction
from .services import PaymentError, normalize_phone, parse_amount


class PaymentForm(forms.Form):
    """Saisie du numéro Mobile Money et de l'opérateur (étape unique, comme un portail de service en ligne)."""

    user_email = forms.EmailField(label="Votre e-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    provider = forms.ChoiceField(label="Opérateur", choices=Transaction.Provider.choices, widget=forms.RadioSelect)
    phone_number = forms.CharField(
        label="Numéro Mobile Money", max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "01 97 00 00 01", "autocomplete": "tel"}),
    )
    # Démo : en production, retirer ce champ et passer le montant de la commande côté serveur
    # (create_transaction(amount=commande.total, ...)).
    amount = forms.DecimalField(label="Montant (FCFA)", min_value=0, decimal_places=0)

    def clean_phone_number(self):
        try:
            return normalize_phone(self.cleaned_data["phone_number"])
        except PaymentError as exc:
            raise forms.ValidationError(str(exc))

    def clean_amount(self):
        try:
            return parse_amount(self.cleaned_data["amount"])
        except PaymentError as exc:
            raise forms.ValidationError(str(exc))
