from django.contrib.auth import get_user_model
from django.utils import timezone


class PhoneOTPBackend:
    """Authentifie un utilisateur après une vérification OTP réussie côté serveur.

    `verified=True` ne peut être passé que par le code serveur (vue de vérification),
    jamais depuis un paramètre HTTP.
    """

    def authenticate(self, request, phone_number=None, verified=False, **kwargs):
        if not verified or not phone_number:
            return None
        User = get_user_model()
        user, _ = User.objects.get_or_create(phone_number=phone_number)
        if not user.is_phone_verified:
            user.is_phone_verified = True
            user.save(update_fields=["is_phone_verified"])
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
