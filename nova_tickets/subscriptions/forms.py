from django import forms

from core.payments import find_method, methods_for_country

GROUPS = [("momo", "Mobile Money"), ("card", "Carte bancaire"), ("wallet", "Portefeuille en ligne"), ("bank", "Virement bancaire")]


class SubscribeForm(forms.Form):
    """Le moyen de paiement doit faire partie de ceux proposés pour le pays de l'organisateur."""
    method = forms.CharField()
    phone = forms.CharField(required=False, max_length=20)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        data = super().clean()
        method = find_method(self.user.country, data.get("method", ""))
        if not method:
            raise forms.ValidationError("Choisissez un moyen de paiement.")
        if method["kind"] == "momo" and not (data.get("phone") or "").strip():
            raise forms.ValidationError("Saisissez votre numéro Mobile Money.")
        data["method_obj"] = method
        return data


def grouped_methods(country):
    """Moyens du pays rangés par famille (Mobile Money, carte, portefeuille, virement) pour l'affichage."""
    pool = methods_for_country(country)
    return [(label, [m for m in pool if m["kind"] == kind]) for kind, label in GROUPS if any(m["kind"] == kind for m in pool)]
