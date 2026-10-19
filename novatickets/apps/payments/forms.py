from django import forms

from apps.accounts.forms import styler
from apps.payments.providers import moyens_pour_pays


class DemandeRetraitForm(forms.Form):
    montant = forms.DecimalField(label="Montant à retirer (FCFA)", min_value=1000, max_digits=12, decimal_places=0)
    moyen = forms.ChoiceField(label="Moyen de retrait")
    numero_compte = forms.CharField(label="Numéro de compte mobile money", max_length=30)

    def __init__(self, *args, pays="BJ", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moyen"].choices = [(p.slug, p.libelle) for p in moyens_pour_pays(pays) if p.slug != "simulation" and p.slug != "carte_bancaire"]
        styler(self.fields)
