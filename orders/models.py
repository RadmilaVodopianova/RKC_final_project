from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Нова"
        PROCESSING = "processing", "В обробці"
        CONFIRMED = "confirmed", "Погоджена"
        COMPLETED = "completed", "Виконана"
        CANCELLED = "cancelled", "Скасована"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Користувач",
    )

    full_name = models.CharField(
        "Ім’я та прізвище",
        max_length=301,
    )

    email = models.EmailField("Електронна пошта")

    phone = models.CharField(
        "Номер телефону",
        max_length=20,
    )

    comment = models.TextField(
        "Коментар до заявки",
        blank=True,
        max_length=2000,
    )

    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    created_at = models.DateTimeField(
        "Дата створення",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "Дата оновлення",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Заявка №{self.pk} — {self.full_name}"


class OrderItem(models.Model):
    class Unit(models.TextChoices):
        KG = "kg", "кг"
        PCS = "pcs", "шт"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заявка",
    )

    product = models.ForeignKey(
        "core.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name="Товар",
    )

    product_name = models.CharField(
        "Назва товару на момент заявки",
        max_length=200,
    )

    quantity = models.DecimalField(
        "Кількість",
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("1000")),
        ],
    )

    unit = models.CharField(
        "Одиниця виміру",
        max_length=3,
        choices=Unit.choices,
    )

    class Meta:
        verbose_name = "Позиція заявки"
        verbose_name_plural = "Позиції заявки"

    def __str__(self):
        return (
            f"{self.product_name} — "
            f"{self.quantity} {self.get_unit_display()}"
        )