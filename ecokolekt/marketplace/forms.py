from django import forms

from operations.models import Site
from traceability.models import WasteBatch

from .models import Listing


class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ["title", "category", "description", "available_kg", "price_per_kg_xof", "site", "batch"]
        labels = {
            "title": "Titre de l'offre",
            "category": "Matière",
            "description": "Description",
            "available_kg": "Quantité disponible (kg)",
            "price_per_kg_xof": "Prix au kg (XOF)",
            "site": "Lieu de stock",
            "batch": "Lot d'origine (traçabilité)",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(owner=user)
        self.fields["batch"].queryset = WasteBatch.objects.filter(holder=user)
        self.fields["site"].required = False
        self.fields["batch"].required = False


class OrderForm(forms.Form):
    quantity_kg = forms.DecimalField(
        label="Quantité souhaitée (kg)", min_value=0.01, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )
