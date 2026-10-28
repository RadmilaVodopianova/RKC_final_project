from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

from .forms import EmailAuthenticationForm

urlpatterns = [
    path(
        "accounts/register/",
        views.register,
        name="register",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "account/",
        views.account,
        name="account",
    ),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
]