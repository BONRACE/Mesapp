from django import forms
from django.forms import inlineformset_factory
from .models import Event, TicketType


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["nom", "description", "lieu", "ville", "visuel", "logo",
                  "date_debut", "date_fin", "date_limite_achat", "heure_debut"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "field-input", "placeholder": "Ex: Conférence Tech Innovate 2026"}),
            "lieu": forms.TextInput(attrs={"class": "field-input", "placeholder": "Ex: Palais des Congrès"}),
            "ville": forms.TextInput(attrs={"class": "field-input", "placeholder": "Ex: Cotonou"}),
            "date_debut": forms.DateInput(attrs={"type": "date", "class": "field-input"}),
            "date_fin": forms.DateInput(attrs={"type": "date", "class": "field-input"}),
            "date_limite_achat": forms.DateInput(attrs={"type": "date", "class": "field-input"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time", "class": "field-input"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "field-input",
                                                   "placeholder": "Quelques lignes sur l'événement (optionnel)"}),
            "visuel": forms.ClearableFileInput(attrs={"class": "hidden", "id": "id_visuel"}),
            "logo": forms.ClearableFileInput(attrs={"class": "hidden", "id": "id_logo"}),
        }


TicketTypeFormSet = inlineformset_factory(
    Event, TicketType,
    fields=["nom", "description", "prix", "quantite_disponible", "couleur_badge"],
    extra=0, can_delete=True,
)
