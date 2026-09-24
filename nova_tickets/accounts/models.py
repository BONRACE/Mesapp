from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur unique de la plateforme : soit spectateur, soit organisateur."""

    class Role(models.TextChoices):
        SPECTATEUR = "spectateur", "Spectateur"
        ORGANISATEUR = "organisateur", "Organisateur"

    class Sexe(models.TextChoices):
        HOMME = "H", "Homme"
        FEMME = "F", "Femme"
        AUTRE = "X", "Autre / Préfère ne pas dire"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SPECTATEUR)

    # Champs communs demandés : nom, prénoms, sexe, profession, photo
    nom = models.CharField(max_length=100, blank=True)
    prenoms = models.CharField(max_length=150, blank=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    profession = models.CharField(max_length=150, blank=True)
    photo = models.ImageField(upload_to="avatars/", blank=True, null=True)
    telephone = models.CharField(max_length=30, blank=True)

    # Champs spécifiques organisateur
    nom_structure = models.CharField(max_length=150, blank=True)
    logo_organisateur = models.ImageField(upload_to="logos_organisateurs/", blank=True, null=True)

    @property
    def nom_complet(self):
        return f"{self.prenoms} {self.nom}".strip() or self.username

    @property
    def is_organisateur(self):
        return self.role == self.Role.ORGANISATEUR

    def __str__(self):
        return self.nom_complet
