from django import forms

from .models import ContactMessage


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage

        fields = (
            "name",
            "email",
            "phone",
            "message",
        )

        widgets = {
            "name": forms.TextInput(
                attrs={"autocomplete": "name"},
            ),
            "email": forms.EmailInput(
                attrs={"autocomplete": "email"},
            ),
            "phone": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": "+380XXXXXXXXX",
                },
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Напишіть ваше запитання",
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