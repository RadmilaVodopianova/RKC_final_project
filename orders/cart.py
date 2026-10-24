from decimal import Decimal

from core.models import Product


class Cart:
    SESSION_KEY = "cart"

    def __init__(self, request):
        self.session = request.session

        if self.SESSION_KEY not in self.session:
            self.session[self.SESSION_KEY] = {}

        self.cart = self.session[self.SESSION_KEY]

    def save(self):
        self.session.modified = True

    def add(self, product, quantity, unit, replace=False):
        if unit not in ("kg", "pcs"):
            raise ValueError("Оберіть кг або шт.")

        quantity = Decimal(str(quantity))
        key = f"{product.pk}_{unit}"

        if not replace and key in self.cart:
            quantity += Decimal(self.cart[key]["quantity"])

        if not quantity.is_finite() or not Decimal("0.01") <= quantity <= 1000:
            raise ValueError(
                "Кількість має бути від 0,01 до 1000."
            )

        if unit == "pcs" and quantity != quantity.to_integral_value():
            raise ValueError(
                "Для штук потрібно вказати цілу кількість."
            )

        self.cart[key] = {
            "product_id": product.pk,
            "quantity": str(quantity),
            "unit": unit,
        }
        self.save()

    def remove(self, product_id, unit):
        key = f"{product_id}_{unit}"

        if key in self.cart:
            del self.cart[key]
            self.save()

    def clear(self):
        self.session[self.SESSION_KEY] = {}
        self.cart = self.session[self.SESSION_KEY]
        self.save()

    def __iter__(self):
        product_ids = [
            item["product_id"]
            for item in self.cart.values()
        ]

        products = Product.objects.filter(
            pk__in=product_ids,
            is_active=True,
        ).in_bulk()

        for item in self.cart.values():
            product = products.get(item["product_id"])

            if product is None:
                continue

            yield {
                "product": product,
                "quantity": Decimal(item["quantity"]),
                "unit": item["unit"],
                "unit_label": (
                    "кг" if item["unit"] == "kg" else "шт"
                ),
            }