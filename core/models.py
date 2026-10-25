from django.conf import settings
from django.db import models


# =========================
# КАТЕГОРИИ ТОВАРОВ
# =========================

class Category(models.Model):
    name = models.CharField(
        "Назва підгрупи",
        max_length=100,
        unique=True,
    )

    slug = models.SlugField(
        "Код для посилання",
        max_length=100,
        unique=True,
    )

    class Meta:
        verbose_name = "Підгрупа"
        verbose_name_plural = "Підгрупи"
        ordering = ["id"]

    def __str__(self):
        return self.name


# =========================
# ТОВАРЫ
# =========================

class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Підгрупа",
    )

    name = models.CharField(
        "Назва товару",
        max_length=200,
    )

    image = models.ImageField(
        "Фото товару",
        upload_to="products/",
        blank=True,
    )

    composition = models.TextField(
        "Склад",
        blank=True,
    )

    nutritional_value = models.TextField(
        "Харчова цінність на 100 г",
        blank=True,
    )

    energy_value = models.CharField(
        "Енергетична цінність на 100 г",
        max_length=200,
        blank=True,
    )

    shelf_life = models.CharField(
        "Строк зберігання",
        max_length=250,
        blank=True,
    )

    storage_conditions = models.TextField(
        "Умови зберігання",
        blank=True,
    )

    is_active = models.BooleanField(
        "Показувати в каталозі",
        default=True,
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


# =========================
# ОБРАЩЕНИЯ С САЙТА
# =========================

class ContactMessage(models.Model):
    name = models.CharField(
        "Ім’я",
        max_length=150,
    )

    email = models.EmailField(
        "Електронна пошта",
    )

    phone = models.CharField(
        "Номер телефону",
        max_length=20,
        blank=True,
    )

    message = models.TextField(
        "Повідомлення",
        max_length=3000,
    )

    is_processed = models.BooleanField(
        "Опрацьовано",
        default=False,
    )

    created_at = models.DateTimeField(
        "Дата надходження",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Звернення"
        verbose_name_plural = "Звернення"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Звернення №{self.pk} — {self.name}"


# =========================
# ИЗБРАННЫЕ ТОВАРЫ ❤️
# =========================

class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Користувач",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Товар",
    )

    created_at = models.DateTimeField(
        "Дата додавання",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Обраний товар"
        verbose_name_plural = "Обрані товари"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_favorite_product",
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.product.name}"