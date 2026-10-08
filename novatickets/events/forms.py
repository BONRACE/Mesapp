from django import forms
from django.forms import inlineformset_factory

from .models import Event, TicketType


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kw):
        super().__init__(format="%Y-%m-%d", **kw)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kw):
        super().__init__(format="%H:%M", **kw)


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "visual", "logo", "description", "location", "start_date", "end_date", "start_time", "purchase_deadline"]
        widgets = {
            "start_date": DateInput(),
            "end_date": DateInput(),
            "purchase_deadline": DateInput(),
            "start_time": TimeInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        data = super().clean()
        start, end, deadline = data.get("start_date"), data.get("end_date"), data.get("purchase_deadline")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin doit être après la date de début.")
        if end and deadline and deadline > end:
            self.add_error("purchase_deadline", "La date limite d'achat ne peut pas dépasser la fin de l'événement.")
        return data


class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = ["name", "price", "stock"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex : Standard, VIP…"}),
            "price": forms.NumberInput(attrs={"min": 0, "placeholder": "5000"}),
            "stock": forms.NumberInput(attrs={"min": 1, "placeholder": "100"}),
        }

    def clean_stock(self):
        stock = self.cleaned_data["stock"]
        if self.instance.pk and stock < self.instance.sold:
            raise forms.ValidationError(f"{self.instance.sold} billets déjà vendus : le stock ne peut pas descendre en dessous.")
        return stock


class BaseTicketFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        kept = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                if form.instance.pk and form.cleaned_data.get("DELETE") and form.instance.sold:
                    raise forms.ValidationError("Impossible de supprimer un type de ticket déjà vendu.")
                continue
            kept += 1
        if kept == 0:
            raise forms.ValidationError("Ajoutez au moins un type de ticket.")


TicketFormSet = inlineformset_factory(
    Event, TicketType, form=TicketTypeForm, formset=BaseTicketFormSet,
    extra=1, can_delete=True, min_num=0, validate_min=False,
)
