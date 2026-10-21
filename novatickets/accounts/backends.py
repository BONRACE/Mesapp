from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Connexion par adresse e-mail (insensible à la casse)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = username or kwargs.get("email")
        if not email or not password:
            return None
        try:
            user = User.objects.get(email__iexact=email.strip())
        except User.DoesNotExist:
            User().set_password(password)  # évite l'attaque par mesure du temps
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
