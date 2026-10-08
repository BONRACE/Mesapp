from django import forms
from django.forms import inlineformset_factory

from accounts.forms import INPUT

from .models import Event, TicketType


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "description", "location", "banner", "logo", "start_date", "end_date", "start_time", "sales_deadline"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "sales_deadline": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            if isinstance(f.widget, forms.FileInput):
                f.widget.attrs.update({
                    "class": "block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-4 file:py-2.5 file:text-emerald-700 file:font-medium",
                    "accept": "image/*",
                })
            else:
                f.widget.attrs["class"] = INPUT

    def clean(self):
        d = super().clean()
        s, e, dl = d.get("start_date"), d.get("end_date"), d.get("sales_deadline")
        if s and e and e < s:
            self.add_error("end_date", "La date de fin doit être après la date de début.")
        if e and dl and dl > e:
            self.add_error("sales_deadline", "La vente doit se terminer au plus tard à la fin de l'événement.")
        return d


class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = ["name", "price", "stock"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex. VIP, Standard…"}),
            "price": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "stock": forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.widget.attrs["class"] = INPUT


class BaseTicketFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        alive = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if not alive:
            raise forms.ValidationError("Ajoutez au moins un type de ticket.")


TicketFormSet = inlineformset_factory(
    Event, TicketType, form=TicketTypeForm, formset=BaseTicketFormSet,
    extra=1, can_delete=True,
)
