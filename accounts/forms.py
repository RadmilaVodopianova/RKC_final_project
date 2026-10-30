from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import Profile

User = get_user_model()


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        label="Ім’я",
        max_length=150,
        required=True,
    )

    last_name = forms.CharField(
        label="Прізвище",
        max_length=150,
        required=True,
    )

    email = forms.EmailField(
        label="Електронна пошта",
        max_length=150,
        required=True,
        widget=forms.EmailInput(
            attrs={"autocomplete": "email"},
        ),
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        ):
            raise forms.ValidationError(
                "Обліковий запис із такою електронною поштою вже існує."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email

        if commit:
            user.save()

        return user

class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Електронна пошта",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "autofocus": True,
            },
        ),
    )

    error_messages = {
        "invalid_login": (
            "Не вдалося увійти. Перевірте email і пароль. Якщо ви щойно подали запит, дочекайтеся схвалення адміністратора."
        ),
        "inactive": "Цей обліковий запис неактивний.",
    }

class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Ім’я",
        max_length=150,
        required=True,
    )

    last_name = forms.CharField(
        label="Прізвище",
        max_length=150,
        required=True,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name")


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("phone",)

        widgets = {
            "phone": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": "+380XXXXXXXXX",
                },
            ),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()

        if not phone:
            return ""

        for character in (" ", "-", "(", ")"):
            phone = phone.replace(character, "")

        digits = phone[1:] if phone.startswith("+") else phone

        if (
            not digits.isascii()
            or not digits.isdigit()
            or not 7 <= len(digits) <= 15
        ):
            raise forms.ValidationError(
                "Вкажіть номер телефону: від 7 до 15 цифр. "
                "На початку можна додати +."
            )

        return phone