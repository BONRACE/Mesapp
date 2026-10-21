from django import forms
from django.forms import inlineformset_factory

from .models import Event, TicketType

INPUT = "nt-input"


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "description", "visual", "logo", "venue", "city",
                  "start_date", "end_date", "start_time", "sales_deadline"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "sales_deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sales_deadline"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        for f in self.fields.values():
            if not isinstance(f.widget, forms.ClearableFileInput):
                f.widget.attrs.setdefault("class", INPUT)
        self.fields["visual"].help_text = "Affiche de l'événement (JPG/PNG, 5 Mo max)."

    def clean(self):
        data = super().clean()
        start, end, deadline = data.get("start_date"), data.get("end_date"), data.get("sales_deadline")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin doit être postérieure à la date de début.")
        if end and deadline and deadline.date() > end:
            self.add_error("sales_deadline", "La date limite d'achat ne peut pas dépasser la fin de l'événement.")
        return data

    def clean_visual(self):
        img = self.cleaned_data.get("visual")
        if img and hasattr(img, "size") and img.size > 5 * 1024 * 1024:
            raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
        return img


class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = ["name", "price", "stock"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex. Standard, VIP…"}),
            "price": forms.NumberInput(attrs={"min": 0, "step": 100}),
            "stock": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", INPUT)

    def clean_stock(self):
        stock = self.cleaned_data["stock"]
        if stock < 1:
            raise forms.ValidationError("Le stock doit être d'au moins 1.")
        if self.instance.pk and stock < self.instance.sold:
            raise forms.ValidationError(f"{self.instance.sold} tickets déjà vendus : le stock ne peut pas être inférieur.")
        return stock


class BaseTicketTypeFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        alive = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if not alive:
            raise forms.ValidationError("Ajoutez au moins un type de ticket.")
        names = [f.cleaned_data["name"].strip().lower() for f in alive]
        if len(names) != len(set(names)):
            raise forms.ValidationError("Deux types de tickets portent le même nom.")
        for f in self.forms:
            if f.cleaned_data.get("DELETE") and f.instance.pk and f.instance.sold:
                raise forms.ValidationError(
                    f"Le type « {f.instance.name} » a déjà des ventes : il ne peut pas être supprimé."
                )


TicketTypeFormSet = inlineformset_factory(
    Event, TicketType, form=TicketTypeForm, formset=BaseTicketTypeFormSet,
    extra=1, can_delete=True,
)
