from django import forms
from django.utils import timezone

from .models import PickupRequest, Site, WasteCategory


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ["kind", "name", "address", "latitude", "longitude", "accepted_categories"]
        labels = {
            "kind": "Type de site",
            "name": "Nom",
            "address": "Adresse",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "accepted_categories": "Matières acceptées",
        }
        widgets = {
            "latitude": forms.NumberInput(attrs={"step": "any", "placeholder": "6.3703"}),
            "longitude": forms.NumberInput(attrs={"step": "any", "placeholder": "2.3912"}),
            "accepted_categories": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = {
            "producer": [Site.Kind.PRODUCTION],
            "collector": [Site.Kind.COLLECTION],
            "recycler": [Site.Kind.RECYCLING],
        }.get(getattr(user, "role", None), [])
        self.fields["kind"].choices = [c for c in Site.Kind.choices if c[0] in allowed]
        self.fields["accepted_categories"].queryset = WasteCategory.objects.all()


class PickupRequestForm(forms.ModelForm):
    window_start = forms.DateTimeField(label="Début de la fenêtre",
                                       widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    window_end = forms.DateTimeField(label="Fin de la fenêtre",
                                     widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    class Meta:
        model = PickupRequest
        fields = ["site", "category", "estimated_kg", "window_start", "window_end"]
        labels = {"site": "Site", "category": "Type de déchet", "estimated_kg": "Poids estimé (kg)"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(owner=user, kind=Site.Kind.PRODUCTION)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("window_start"), cleaned.get("window_end")
        if start and end:
            if end <= start:
                raise forms.ValidationError("La fin de la fenêtre doit être après le début.")
            if start < timezone.now():
                raise forms.ValidationError("La fenêtre d'enlèvement ne peut pas être dans le passé.")
        return cleaned


class RoutePlanForm(forms.Form):
    planned_for = forms.DateField(label="Date de la tournée",
                                  widget=forms.DateInput(attrs={"type": "date"}))
    depot = forms.ModelChoiceField(label="Point de départ", queryset=Site.objects.none())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["depot"].queryset = Site.objects.filter(owner=user, kind=Site.Kind.COLLECTION)


class ActualWeightForm(forms.Form):
    actual_kg = forms.DecimalField(label="Poids réel collecté (kg)", min_value=0.01, max_digits=8, decimal_places=2)
