from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import (
    ProfileUpdateForm,
    RegistrationForm,
    UserUpdateForm,
)
from .models import Profile


def register(request):
    if request.user.is_authenticated:
        return redirect("account")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                Profile.objects.create(user=user)

            login(request, user)
            return redirect("account")
    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


@login_required
def account(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
    )

    if request.method == "POST":
        user_form = UserUpdateForm(
            request.POST,
            instance=request.user,
        )
        profile_form = ProfileUpdateForm(
            request.POST,
            instance=profile,
        )

        user_is_valid = user_form.is_valid()
        profile_is_valid = profile_form.is_valid()

        if user_is_valid and profile_is_valid:
            with transaction.atomic():
                user_form.save()
                profile_form.save()

            messages.success(
                request,
                "Особисті дані успішно збережено.",
            )
            return redirect("account")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    orders = request.user.orders.order_by(
        "-created_at",
        "-pk",
    )

    return render(
        request,
        "accounts/account.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,
            "orders": orders,
        },
    )