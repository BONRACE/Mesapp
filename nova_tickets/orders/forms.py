from django import forms

from events.models import TicketType


class BuyForm(forms.Form):
    ticket_type = forms.ModelChoiceField(queryset=TicketType.objects.none())
    quantity = forms.IntegerField(min_value=1, max_value=10, initial=1)

    # Réserver pour un ami
    for_friend = forms.BooleanField(required=False)
    friend_last_name = forms.CharField(required=False, max_length=80)
    friend_first_name = forms.CharField(required=False, max_length=80)
    friend_sexe = forms.ChoiceField(required=False, choices=[("", ""), ("M", "Masculin"), ("F", "Féminin")])
    friend_email = forms.EmailField(required=False)
    friend_phone = forms.CharField(required=False, max_length=30)
    friend_photo = forms.ImageField(required=False)

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ticket_type"].queryset = event.ticket_types.all()

    def clean(self):
        data = super().clean()
        if data.get("for_friend"):
            labels = {"friend_last_name": "le nom", "friend_first_name": "les prénoms", "friend_sexe": "le sexe"}
            for f, label in labels.items():
                if not data.get(f):
                    self.add_error(f, f"Indiquez {label} de votre ami.")
        return data
