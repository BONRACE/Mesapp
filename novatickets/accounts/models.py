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
