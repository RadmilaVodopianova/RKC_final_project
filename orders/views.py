from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Product

from .cart import Cart
from .forms import CartQuantityForm


def cart_detail(request):
    cart = Cart(request)
    items = list(cart)

    for item in items:
        item["form"] = CartQuantityForm(
            initial={
                "quantity": item["quantity"],
                "unit": item["unit"],
            },
        )

    return render(
        request,
        "orders/cart.html",
        {"items": items},
    )


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
    )
    form = CartQuantityForm(request.POST)

    if form.is_valid():
        try:
            Cart(request).add(
                product,
                form.cleaned_data["quantity"],
                form.cleaned_data["unit"],
            )
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Товар додано до кошика.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    return redirect("cart_detail")


@require_POST
def cart_update(request, product_id, unit):
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
    )

    # Оновлюємо кількість у поточній одиниці виміру.
    data = request.POST.copy()
    data["unit"] = unit
    form = CartQuantityForm(data)

    if form.is_valid():
        try:
            Cart(request).add(
                product,
                form.cleaned_data["quantity"],
                form.cleaned_data["unit"],
                replace=True,
            )
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Кількість оновлено.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    return redirect("cart_detail")


@require_POST
def cart_remove(request, product_id, unit):
    if unit not in ("kg", "pcs"):
        messages.error(request, "Неправильна одиниця виміру.")
        return redirect("cart_detail")

    Cart(request).remove(product_id, unit)
    messages.success(request, "Позицію видалено з кошика.")

    return redirect("cart_detail")