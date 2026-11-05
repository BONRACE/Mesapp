from django.contrib.auth.models import AbstractUser
from django.db import models

from core.countries import COUNTRY_CHOICES, DEFAULT_COUNTRY, DIAL_BY_CODE


class User(AbstractUser):
    class Role(models.TextChoices):
        SPECTATEUR = "spectateur", "Spectateur"
        ORGANISATEUR = "organisateur", "Organisateur"

    class Sexe(models.TextChoices):
        HOMME = "M", "Homme"
        FEMME = "F", "Femme"

    email = models.EmailField("E-mail", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SPECTATEUR)
    country = models.CharField("Pays", max_length=2, choices=COUNTRY_CHOICES, default=DEFAULT_COUNTRY)
    phone = models.CharField("Téléphone mobile", max_length=20)  # format international : +22997000000
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    profession = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="users/photos/", blank=True, null=True)
    org_name = models.CharField("Nom de l'organisation", max_length=150, blank=True)
    org_logo = models.ImageField(upload_to="users/org_logos/", blank=True, null=True)
    signature = models.CharField("Signature (nom et fonction)", max_length=120, blank=True,
                                 help_text="Affichée en bas des reçus et billets. Ex : Adama Touré – Directeur")

    class SignatureMode(models.TextChoices):
        IMAGE = "image", "Signature manuscrite"
        ORGANIZER = "organizer", "Signature avec le nom de l'organisateur"
        MANAGER = "manager", "Signature avec le nom du manager"

    signature_mode = models.CharField("Type de signature", max_length=10, choices=SignatureMode.choices, default=SignatureMode.ORGANIZER)
    signature_image = models.ImageField("Signature manuscrite", upload_to="users/signatures/", blank=True, null=True)

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANISATEUR

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def ticket_name(self):
        """Nom affiché sur le billet : NOM Prénoms."""
        return f"{self.last_name.upper()} {self.first_name}".strip()

    @property
    def signature_text(self):
        """Signature textuelle de l'organisateur (ou de son manager) sur les reçus."""
        if self.signature_mode == self.SignatureMode.MANAGER:
            return self.signature or self.display_name
        if self.signature_mode == self.SignatureMode.ORGANIZER:
            return self.display_name
        return self.signature or self.display_name      # mode manuscrit : texte de secours si l'image est illisible

    @property
    def signature_png(self):
        """Signature manuscrite en PNG (bytes) si le mode « manuscrite » est choisi et l'image lisible, sinon None."""
        if self.signature_mode != self.SignatureMode.IMAGE or not self.signature_image:
            return None
        try:
            from PIL import Image
            import io
            with Image.open(self.signature_image.path) as im:
                im = im.convert("RGBA")
                im.thumbnail((600, 200))
                out = io.BytesIO()
                im.save(out, "PNG", optimize=True)
                return out.getvalue()
        except Exception:
            return None

    @property
    def organizer_label(self):
        return self.org_name or self.display_name

    @property
    def initials(self):
        return ((self.first_name[:1] + self.last_name[:1]) or self.email[:1]).upper()

    @property
    def local_phone(self):
        dial = str(DIAL_BY_CODE.get(self.country, ""))
        if dial and self.phone.startswith("+" + dial):
            return self.phone[len(dial) + 1:]
        return self.phone.lstrip("+")

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"
