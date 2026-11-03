import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse


def new_slug():
    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y").lower()


class BusinessCard(models.Model):
    """Carte de visite numérique d'un participant, partageable depuis son billet (lien, QR, fichier vCard)."""

    class Theme(models.TextChoices):
        """Palette de couleurs (classe CSS .t-<valeur> dans card.css)."""
        GREEN = "green", "Vert Nova"
        FOREST = "forest", "Forêt"
        MINT = "mint", "Menthe"
        OCEAN = "ocean", "Océan"
        NAVY = "navy", "Bleu Nova"
        SUNSET = "sunset", "Soleil"
        VIOLET = "violet", "Violet"
        ROSE = "rose", "Rose"
        GOLD = "gold", "Or"
        GRAPHITE = "graphite", "Graphite"

    class Layout(models.TextChoices):
        """Mise en page (classe CSS .l-<valeur> dans card.css)."""
        CLASSIC = "classic", "Classique"
        CENTER = "center", "Centré"
        SPLIT = "split", "Deux volets"
        MINIMAL = "minimal", "Minimal"
        BOLD = "bold", "Affiche"
        WAX = "wax", "Pagne recto/verso"
        WAXTOP = "waxtop", "Pagne verso"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_card")
    slug = models.SlugField(max_length=16, unique=True, default=new_slug, editable=False)

    full_name = models.CharField("Nom complet", max_length=120)
    job_title = models.CharField("Fonction", max_length=120, blank=True)
    company = models.CharField("Entreprise / organisation", max_length=120, blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField("E-mail professionnel", blank=True)
    website = models.URLField("Site web", blank=True)
    linkedin = models.URLField("LinkedIn", blank=True)
    city = models.CharField("Ville / pays", max_length=80, blank=True)
    bio = models.CharField("Présentation (160 car. max)", max_length=160, blank=True)
    theme = models.CharField("Couleur", max_length=10, choices=Theme.choices, default=Theme.GREEN)
    layout = models.CharField("Style de carte", max_length=10, choices=Layout.choices, default=Layout.CLASSIC)
    show_on_ticket = models.BooleanField("Afficher le partage sur mes billets", default=True)

    # Le partage public n'est possible qu'une fois la carte activée (paiement Mobile Money, cf. BUSINESS_CARD_PRICE).
    is_active = models.BooleanField("Activée", default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carte de {self.full_name}"

    def get_absolute_url(self):
        return reverse("cards:public", args=[self.slug])

    @property
    def public_url(self):
        return settings.SITE_URL.rstrip("/") + self.get_absolute_url()

    @property
    def initials(self):
        parts = self.full_name.split()
        return ("".join(p[0] for p in parts[:2]) or "?").upper()

    @property
    def photo(self):
        return self.user.photo
