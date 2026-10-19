from django import forms
from django.forms import inlineformset_factory

from apps.accounts.forms import CLASSE_CHAMP, CLASSE_FICHIER, styler

from .models import Evenement, TypeTicket


class EvenementForm(forms.ModelForm):
    class Meta:
        model = Evenement
        fields = [
            "nom", "description", "visuel", "logo", "lieu", "ville",
            "date_debut", "heure_debut", "date_fin", "date_limite_achat",
        ]
        labels = {
            "nom": "Nom de l'événement",
            "visuel": "Visuel de l'événement",
            "logo": "Logo de l'événement",
            "heure_debut": "Heure de début",
            "date_debut": "Date de début",
            "date_fin": "Date de fin",
            "date_limite_achat": "Date limite d'achat",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "date_limite_achat": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styler(self.fields)
        self.fields["visuel"].widget.attrs["class"] = CLASSE_FICHIER
        self.fields["logo"].widget.attrs["class"] = CLASSE_FICHIER
        self.fields["date_limite_achat"].input_formats = ["%Y-%m-%dT%H:%M"]


class TypeTicketForm(forms.ModelForm):
    class Meta:
        model = TypeTicket
        fields = ["nom", "prix", "stock"]
        labels = {"nom": "Type de ticket", "prix": "Prix (FCFA)", "stock": "Stock"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styler(self.fields)
        self.fields["prix"].widget.attrs.update({"min": "0", "inputmode": "numeric"})
        self.fields["stock"].widget.attrs.update({"min": "1", "inputmode": "numeric"})

    def clean_prix(self):
        prix = self.cleaned_data["prix"]
        if prix is None or prix < 0:
            raise forms.ValidationError("Le prix ne peut pas être négatif.")
        return prix


TypeTicketFormSet = inlineformset_factory(
    Evenement,
    TypeTicket,
    form=TypeTicketForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
