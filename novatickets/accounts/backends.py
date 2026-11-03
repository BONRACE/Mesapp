from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Connexion avec l'e-mail OU le nom d'utilisateur (sans tenir compte des majuscules)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        username = username or kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None
        identifier = username.strip()
        user = (User.objects.filter(email__iexact=identifier).first()
                or User.objects.filter(username__iexact=identifier).first())
        if user is None:
            User().set_password(password)          # temps de réponse constant : pas d'énumération de comptes
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
