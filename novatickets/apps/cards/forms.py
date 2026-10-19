from django import forms

from apps.accounts.forms import styler

from .models import CarteVisite


class CarteVisiteForm(forms.ModelForm):
    class Meta:
        model = CarteVisite
        fields = ["theme", "nom_entreprise", "nom_contact", "poste", "telephone", "email",
                  "site_web", "adresse", "slogan", "logo"]
        widgets = {"theme": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styler(self.fields)
        self.fields["theme"].widget.attrs.pop("class", None)
        self.fields["logo"].widget.attrs["class"] = (
            "w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm"
        )
