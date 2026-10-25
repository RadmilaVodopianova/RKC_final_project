
from django.urls import path
from . import views

urlpatterns = [
    # Головна сторінка
    path("", views.home, name="home"),

    # Про підприємство
    path("about/", views.about, name="about"),

    # Контакти
    path("contacts/", views.contacts, name="contacts"),

    # Каталог продукції
    path("catalog/", views.catalog, name="catalog"),

    # Сторінка окремого товару
    path(
        "catalog/<int:pk>/",
        views.product_detail,
        name="product_detail"
    ),

    # Обрані товари
    path(
        "favorites/",
        views.favorites,
        name="favorites"
    ),

    # Додати або видалити товар з обраного
    path(
        "favorites/toggle/<int:pk>/",
        views.toggle_favorite,
        name="toggle_favorite"
    ),

    # Політика конфіденційності
    path("privacy/", views.privacy, name="privacy"),
]
