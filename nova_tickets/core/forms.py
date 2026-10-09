from django import forms

from accounts.forms import INPUT

from .models import BusinessCard


class CardForm(forms.ModelForm):
    class Meta:
        model = BusinessCard
        fields = ["company_name", "tagline", "contact_name", "job_title", "phone", "email", "website", "address", "logo", "color"]
        widgets = {
            "color": forms.RadioSelect,
            "phone": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+229 97 00 00 00"}),
            "website": forms.TextInput(attrs={"placeholder": "www.monentreprise.com"}),
            "tagline": forms.TextInput(attrs={"placeholder": "Ex. Organisation d'événements"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if name == "color":
                continue
            if isinstance(f.widget, forms.FileInput):
                f.widget.attrs.update({
                    "class": "block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-4 file:py-2.5 file:font-medium file:text-emerald-700",
                    "accept": "image/*",
                })
            else:
                f.widget.attrs["class"] = INPUT
        self.fields["color"].choices = BusinessCard.COLORS
        self.fields["color"].initial = "#059669"

    def clean(self):
        data = super().clean()
        if not data.get("phone") and not data.get("email"):
            raise forms.ValidationError("Indiquez au moins un téléphone ou un e-mail pour être joignable.")
        return data
