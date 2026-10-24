from decimal import Decimal

from django import forms
from .models import Order

class CartQuantityForm(forms.Form):
    UNIT_CHOICES = [
        ("kg", "кг"),
        ("pcs", "шт"),
    ]

    quantity = forms.DecimalField(
        label="Кількість",
        min_value=Decimal("0.01"),
        max_value=Decimal("1000"),
        max_digits=6,
        decimal_places=2,
        initial=1,
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "1000",
                "step": "0.01",
            },
        ),
        error_messages={
            "required": "Вкажіть кількість товару.",
            "invalid": "Введіть коректну кількість.",
            "min_value": "Кількість має бути не меншою за 0,01.",
            "max_value": "Кількість має бути не більшою за 1000.",
        },
    )

    unit = forms.ChoiceField(
        label="Одиниця виміру",
        choices=UNIT_CHOICES,
        initial="kg",
        error_messages={
            "required": "Оберіть одиницю виміру.",
            "invalid_choice": "Оберіть кг або шт.",
        },
    )

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        unit = cleaned_data.get("unit")

        if quantity is not None and unit == "pcs":
            if quantity != quantity.to_integral_value():
                self.add_error(
                    "quantity",
                    "Для штук вкажіть цілу кількість: 1, 2, 3 тощо.",
                )

        return cleaned_data

class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order

        fields = (
            "full_name",
            "email",
            "phone",
            "comment",
        )

        widgets = {
            "full_name": forms.TextInput(
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
            "comment": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Побажання до заявки або зручний час для зв’язку"
                    ),
                },
            ),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()

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