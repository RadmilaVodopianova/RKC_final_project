from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(
        self,
        request,
        username=None,
        password=None,
        **kwargs,
    ):
        if username is None or password is None:
            return None

        identifier = username.strip()

        # Зберігаємо можливість входу в адмінку за старим логіном.
        if "@" not in identifier:
            return super().authenticate(
                request,
                username=identifier,
                password=password,
                **kwargs,
            )

        try:
            user = User.objects.get(email__iexact=identifier)
        except User.DoesNotExist:
            # Виконуємо хешування навіть для невідомого email.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Не обираємо користувача, якщо email дублюється.
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None