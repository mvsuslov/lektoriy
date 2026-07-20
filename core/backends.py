from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Вход по email + пароль вместо username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = (username or "").strip().lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
