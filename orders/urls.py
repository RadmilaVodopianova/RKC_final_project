
from django.urls import path

from . import views


urlpatterns = [
    # Кошик заявки
    path(
        "cart/",
        views.cart_detail,
        name="cart_detail",
    ),

    # Додавання товару до кошика
    path(
        "cart/add/<int:product_id>/",
        views.cart_add,
        name="cart_add",
    ),

    # Оновлення кількості товару
    path(
        "cart/update/<int:product_id>/<str:unit>/",
        views.cart_update,
        name="cart_update",
    ),

    # Видалення товару з кошика
    path(
        "cart/remove/<int:product_id>/<str:unit>/",
        views.cart_remove,
        name="cart_remove",
    ),

    # Оформлення нової заявки
    path(
        "orders/create/",
        views.order_create,
        name="order_create",
    ),

    # Повторення попередньої заявки
    path(
        "orders/<int:pk>/repeat/",
        views.order_repeat,
        name="order_repeat",
    ),

    # Скасування нової заявки її власником
    path(
        "orders/<int:pk>/cancel/",
        views.order_cancel,
        name="order_cancel",
    ),

    # Деталі заявки
    path(
        "orders/<int:pk>/",
        views.order_detail,
        name="order_detail",
    ),
]
