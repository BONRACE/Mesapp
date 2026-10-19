import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.gis.db import models as gis
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("is_approved", True)
        extra.setdefault("profile_completed", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CITIZEN = "citizen", "Citoyen"
        COLLECTOR = "collector", "Collecteur"
        RECYCLER = "recycler", "Recycleur"
        ADMIN = "admin", "Administration"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField("Téléphone (E.164)", max_length=16, unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CITIZEN)
    is_approved = models.BooleanField(
        default=True, help_text="Les collecteurs et recycleurs doivent être validés avant d'opérer."
    )
    profile_completed = models.BooleanField(default=False)
    eco_points = models.PositiveIntegerField(default=0)
    location = gis.PointField(geography=True, null=True, blank=True, srid=4326)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return f"{self.full_name or 'Sans nom'} ({self.phone})"


class CollectorProfile(models.Model):
    class Vehicle(models.TextChoices):
        FOOT = "foot", "À pied / pousse-pousse"
        MOTO = "moto", "Moto / tricycle"
        TRUCK = "truck", "Camion"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collector")
    vehicle_type = models.CharField(max_length=8, choices=Vehicle.choices, default=Vehicle.MOTO)
    capacity_kg = models.PositiveIntegerField(default=200)
    is_on_duty = models.BooleanField(default=False)
    current_location = gis.PointField(geography=True, null=True, blank=True, srid=4326)
    last_seen = models.DateTimeField(null=True, blank=True)


class RecyclerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recycler")
    company_name = models.CharField(max_length=140, blank=True)
    address = models.CharField(max_length=255, blank=True)


class OTPCode(models.Model):
    """Code à usage unique, stocké sous forme de HMAC (jamais en clair)."""

    phone = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "-created_at"])]
