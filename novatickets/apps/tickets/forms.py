from django import forms

from apps.accounts.forms import CLASSE_CHAMP, styler
from apps.events.models import TypeTicket

from apps.accounts.models import Sexe


class AchatForm(forms.Form):
    """Sélection d'un type de ticket et d'une quantité, pour soi-même ou un ami."""

    type_ticket = forms.ModelChoiceField(queryset=TypeTicket.objects.none(), label="Type de ticket")
    quantite = forms.IntegerField(label="Quantité", min_value=1, max_value=10, initial=1)
    pour_un_ami = forms.BooleanField(label="Réserver pour un ami", required=False)
    ami_prenom = forms.CharField(label="Prénom de l'ami", max_length=150, required=False)
    ami_nom = forms.CharField(label="Nom de l'ami", max_length=150, required=False)
    ami_contact = forms.CharField(label="E-mail ou téléphone de l'ami", max_length=190, required=False)
    ami_sexe = forms.ChoiceField(label="Sexe", choices=[("", "—")] + list(Sexe.choices), required=False)

    def __init__(self, *args, evenement=None, **kwargs):
        super().__init__(*args, **kwargs)
        if evenement is not None:
            self.fields["type_ticket"].queryset = evenement.types_tickets.all()
        styler(self.fields)
        self.fields["pour_un_ami"].widget.attrs["class"] = "h-5 w-5 rounded border-slate-300 text-emerald-600"

    def clean(self):
        data = super().clean()
        if data.get("pour_un_ami"):
            for champ, label in [("ami_prenom", "prénom"), ("ami_nom", "nom"), ("ami_contact", "e-mail ou téléphone")]:
                if not data.get(champ):
                    self.add_error(champ, f"Le {label} de l'ami est obligatoire.")
        return data


class ChoixMoyenForm(forms.Form):
    moyen = forms.CharField(widget=forms.HiddenInput)
    telephone_payeur = forms.CharField(label="Numéro qui paie", max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styler(self.fields)
