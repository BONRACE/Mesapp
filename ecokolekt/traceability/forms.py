from django import forms

from .models import EventType

ROLE_EVENT_TYPES = {
    "collector": [EventType.TRANSFERRED],
    "recycler": [EventType.RECEIVED, EventType.PROCESSED, EventType.SOLD],
}


def allowed_event_types(user):
    return ROLE_EVENT_TYPES.get(getattr(user, "role", None), [])


class BatchEventForm(forms.Form):
    event_type = forms.ChoiceField(label="Action")
    note = forms.CharField(label="Note", max_length=255, required=False)
    latitude = forms.FloatField(required=False, min_value=-90, max_value=90, widget=forms.HiddenInput)
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180, widget=forms.HiddenInput)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = allowed_event_types(user)
        self.fields["event_type"].choices = [c for c in EventType.choices if c[0] in allowed]
