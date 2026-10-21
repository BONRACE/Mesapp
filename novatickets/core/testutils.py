"""Outils partagés par les tests."""
import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from accounts.models import User
from events.models import Event, TicketType

_TMP_MEDIA = tempfile.mkdtemp(prefix="nt-test-media-")
media_override = override_settings(MEDIA_ROOT=_TMP_MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")


def cleanup_media():
    shutil.rmtree(_TMP_MEDIA, ignore_errors=True)


def image_file(name="x.png", color=(30, 140, 70), size=(300, 200)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def make_user(email, role="spectateur", country="BJ", phone="+2290197123456", **extra):
    extra.setdefault("first_name", "Test")
    extra.setdefault("last_name", "USER")
    extra.setdefault("sexe", "M")
    if role == "organisateur":
        extra.setdefault("organisation_name", "Orga Test")
    return User.objects.create_user(email, "Pass12345!x", role=role, country=country, phone=phone, **extra)


def make_event(organizer, name="Concert Test", published=True, price=5000, stock=10, days=10):
    start = timezone.localdate() + timedelta(days=days)
    ev = Event(organizer=organizer, name=name, start_date=start, end_date=start, start_time="19:00",
               sales_deadline=timezone.now() + timedelta(days=days - 1), is_published=published, venue="Salle A", city="Cotonou")
    ev.visual.save("v.png", image_file(), save=False)
    ev.save()
    TicketType.objects.create(event=ev, name="Standard", price=price, stock=stock)
    return ev
