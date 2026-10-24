from django.urls import path

from . import views


urlpatterns = [
    path(
        "cart/",
        views.cart_detail,
        name="cart_detail",
    ),
    path(
        "cart/add/<int:product_id>/",
        views.cart_add,
        name="cart_add",
    ),
    path(
        "cart/update/<int:product_id>/<str:unit>/",
        views.cart_update,
        name="cart_update",
    ),
    path(
        "cart/remove/<int:product_id>/<str:unit>/",
        views.cart_remove,
        name="cart_remove",
    ),
    path(
        "orders/create/",
        views.order_create,
        name="order_create",
    ),
    path(
        "orders/<int:pk>/",
        views.order_detail,
        name="order_detail",
    ),
]