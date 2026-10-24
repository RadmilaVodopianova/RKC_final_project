from decimal import Decimal

from django import forms


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