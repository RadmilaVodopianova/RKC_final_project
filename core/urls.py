from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contacts/", views.contacts, name="contacts"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:pk>/", views.product_detail, name="product_detail"),
    path("privacy/", views.privacy, name="privacy"),
]