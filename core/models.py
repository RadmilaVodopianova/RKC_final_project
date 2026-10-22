from django.db import models


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