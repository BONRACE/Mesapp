import re

import phonenumbers
from django import forms

from core.countries import DIAL_BY_CODE

from .catalog import BANK, CHANNELS, EMAIL, PHONE, channels_for_country
from .models import PayoutMethod

MAX_METHODS = 8


class PayoutMethodForm(forms.ModelForm):
    """Formulaire adapté au pays de l'organisateur : seuls ses canaux locaux (+ banque, PayPal) sont proposés."""

    class Meta:
        model = PayoutMethod
        fields = ["kind", "label", "account_holder", "account_number", "bank_name", "is_default"]
        widgets = {"kind": forms.RadioSelect, "account_number": forms.TextInput(attrs={"autocomplete": "off"})}

    def __init__(self, *args, organizer, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizer = organizer
        allowed = channels_for_country(organizer.country)
        self.fields["kind"].choices = [(k, v["label"]) for k, v in allowed.items()]
        self.fields["bank_name"].required = False
        if not self.instance.pk:
            self.fields["account_holder"].initial = organizer.display_name
            self.fields["is_default"].initial = not organizer.payout_methods.exists()

    def clean(self):
        data = super().clean()
        kind, raw = data.get("kind"), (data.get("account_number") or "").strip()
        if not kind or not raw:
            return data
        ctype = CHANNELS[kind]["type"]
        if ctype == PHONE:
            dial = str(DIAL_BY_CODE.get(self.organizer.country, ""))
            digits = re.sub(r"\D", "", raw)
            if raw.startswith("+") and digits.startswith(dial):
                digits = digits[len(dial):]
            full = f"+{dial}{digits}"
            try:
                ok = phonenumbers.is_possible_number(phonenumbers.parse(full))
            except phonenumbers.NumberParseException:
                ok = False
            if not ok:
                self.add_error("account_number", "Numéro Mobile Money invalide pour votre pays.")
            data["account_number"] = full
        elif ctype == BANK:
            compact = re.sub(r"[\s-]", "", raw).upper()
            if not re.fullmatch(r"[A-Z0-9]{10,34}", compact):
                self.add_error("account_number", "IBAN / RIB invalide (10 à 34 lettres ou chiffres).")
            if not (data.get("bank_name") or "").strip():
                self.add_error("bank_name", "Indiquez le nom de la banque.")
            data["account_number"] = compact
        elif ctype == EMAIL:
            try:
                forms.EmailField().clean(raw)
            except forms.ValidationError:
                self.add_error("account_number", "Adresse e-mail PayPal invalide.")
            data["account_number"] = raw.lower()
        if kind != "bank":
            data["bank_name"] = ""

        duplicate = PayoutMethod.objects.filter(organizer=self.organizer, kind=kind, account_number=data["account_number"])
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            self.add_error("account_number", "Ce moyen de retrait est déjà enregistré.")
        if not self.instance.pk and self.organizer.payout_methods.count() >= MAX_METHODS:
            raise forms.ValidationError(f"Vous pouvez enregistrer {MAX_METHODS} moyens de retrait au maximum.")
        return data
