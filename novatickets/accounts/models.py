from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.countries import country_name, format_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email).lower()
        extra.setdefault("username", email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractUser):
    """Utilisateur NovaTickets : spectateur ou organisateur.

    `last_name` = nom, `first_name` = prénoms.
    """

    class Role(models.TextChoices):
        SPECTATEUR = "spectateur", "Spectateur"
        ORGANISATEUR = "organisateur", "Organisateur"

    class Sexe(models.TextChoices):
        HOMME = "M", "Homme"
        FEMME = "F", "Femme"

    email = models.EmailField("e-mail", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SPECTATEUR)
    country = models.CharField("pays", max_length=2, default="BJ")
    phone = models.CharField("téléphone mobile", max_length=20)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    profession = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="profils/", blank=True)
    # Organisateurs uniquement
    organisation_name = models.CharField("nom de l'organisation", max_length=150, blank=True)
    organisation_logo = models.ImageField(upload_to="organisations/", blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    objects = UserManager()

    @property
    def is_organisateur(self):
        return self.role == self.Role.ORGANISATEUR

    @property
    def is_spectateur(self):
        return self.role == self.Role.SPECTATEUR

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def display_org(self):
        return self.organisation_name or self.full_name

    @property
    def country_name(self):
        return country_name(self.country)

    @property
    def phone_display(self):
        return format_phone(self.phone)

    def __str__(self):
        return f"{self.full_name} <{self.email}>"
