from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    PRODUCER = "producer", "Producteur"
    COLLECTOR = "collector", "Transporteur / collecteur"
    RECYCLER = "recycler", "Grossiste / centre de recyclage"


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Utilisateur authentifié par numéro de téléphone (OTP)."""

    phone_number = models.CharField("téléphone", max_length=20, unique=True)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.PRODUCER)
    full_name = models.CharField("nom complet", max_length=150, blank=True)
    organization = models.CharField("structure", max_length=150, blank=True)
    district = models.CharField("quartier / commune", max_length=100, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    is_onboarded = models.BooleanField("profil complété", default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.full_name or self.phone_number

    @property
    def display_name(self):
        return self.full_name or self.organization or self.phone_number


class OTPCode(models.Model):
    """Code à usage unique. Seul le hash HMAC est stocké, jamais le code."""

    phone_number = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone_number", "created_at"])]

    def is_usable(self):
        return not self.consumed and self.expires_at > timezone.now()
