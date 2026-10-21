from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from core.countries import normalize_phone_any
from events.models import TicketType

from .services import check_can_buy

INPUT = "nt-input"


class PurchaseForm(forms.Form):
    """Choix du ticket + réservation optionnelle pour un ami."""

    ticket_type = forms.ModelChoiceField(queryset=TicketType.objects.none(), widget=forms.RadioSelect, empty_label=None,
                                         label="Type de ticket")
    quantity = forms.IntegerField(label="Quantité", min_value=1, max_value=settings.MAX_TICKETS_PER_ORDER, initial=1,
                                  widget=forms.NumberInput(attrs={"class": INPUT}))
    for_friend = forms.BooleanField(label="Réserver pour un ami (le ticket sera à son nom)", required=False)
    friend_last_name = forms.CharField(label="Nom", max_length=100, required=False)
    friend_first_name = forms.CharField(label="Prénoms", max_length=100, required=False)
    friend_email = forms.EmailField(label="E-mail", required=False)
    friend_phone = forms.CharField(label="Téléphone", max_length=30, required=False,
                                   help_text="Avec l'indicatif (+229…) ou numéro de votre pays.")
    friend_sexe = forms.ChoiceField(label="Sexe", required=False,
                                    choices=[("", "— Non précisé —"), ("M", "Homme"), ("F", "Femme")])
    friend_photo = forms.ImageField(label="Photo de l'ami (facultatif)", required=False)

    def __init__(self, *args, event, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.event, self.user = event, user
        self.fields["ticket_type"].queryset = event.ticket_types.all()
        for name in ("friend_last_name", "friend_first_name", "friend_email", "friend_phone", "friend_sexe"):
            self.fields[name].widget.attrs["class"] = INPUT

    def clean(self):
        data = super().clean()
        ttype, qty = data.get("ticket_type"), data.get("quantity")
        if ttype and qty:
            try:
                check_can_buy(self.user, ttype, qty)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages)
        if data.get("for_friend"):
            for f in ("friend_last_name", "friend_first_name"):
                if not data.get(f):
                    self.add_error(f, "Obligatoire pour une réservation à un ami.")
            email, phone = data.get("friend_email"), data.get("friend_phone")
            if not email and not phone:
                self.add_error("friend_email", "Indiquez au moins l'e-mail ou le téléphone de votre ami.")
            if phone:
                try:
                    data["friend_phone"] = normalize_phone_any(phone, self.user.country)
                except ValidationError as exc:
                    self.add_error("friend_phone", exc)
        return data

    def recipient(self):
        d = self.cleaned_data
        if not d.get("for_friend"):
            return None
        return {"first_name": d["friend_first_name"], "last_name": d["friend_last_name"],
                "email": d.get("friend_email", ""), "phone": d.get("friend_phone", ""),
                "sexe": d.get("friend_sexe", ""), "photo": d.get("friend_photo")}
