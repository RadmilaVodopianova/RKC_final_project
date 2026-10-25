from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Product

from .cart import Cart
from .forms import CartQuantityForm, OrderCreateForm
from .models import Order, OrderItem


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


@login_required
def order_create(request):
    cart = Cart(request)
    items = list(cart)

    if not items:
        messages.info(
            request,
            "Додайте товари до кошика перед оформленням заявки.",
        )
        return redirect("cart_detail")

    if request.method == "POST":
        form = OrderCreateForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = (
                    get_user_model().objects
                    .select_for_update()
                    .get(pk=request.user.pk)
                )

                last_number = (
                    Order.objects.filter(user=user)
                    .aggregate(last=Max("customer_number"))["last"]
                    or 0
                )

                order = form.save(commit=False)
                order.user = user
                order.customer_number = last_number + 1
                order.save()

                for item in items:
                    order_item = OrderItem(
                        order=order,
                        product=item["product"],
                        product_name=item["product"].name,
                        quantity=item["quantity"],
                        unit=item["unit"],
                    )
                    order_item.full_clean()
                    order_item.save()

            cart.clear()

            messages.success(
                request,
                f"Заявку №{order.customer_number} успішно створено.",
            )

            return redirect("order_detail", pk=order.pk)
    else:
        profile = getattr(request.user, "profile", None)

        form = OrderCreateForm(
            initial={
                "full_name": request.user.get_full_name(),
                "email": request.user.email,
                "phone": profile.phone if profile else "",
            },
        )

    return render(
        request,
        "orders/order_create.html",
        {
            "form": form,
            "items": items,
        },
    )


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "orders/order_detail.html",
        {"order": order},
    )

# =========================
# ПОВТОРЕННЯ ПОПЕРЕДНЬОЇ ЗАЯВКИ
# =========================

@login_required
@require_POST
def order_repeat(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=pk,
        user=request.user,
    )

    cart = Cart(request)

    added_count = 0
    skipped_count = 0

    for item in order.items.all():
        product = item.product

        # Перевіряємо, чи товар ще доступний у каталозі
        if product is None or not product.is_active:
            skipped_count += 1
            continue

        # Перевіряємо кількість та одиницю виміру
        form = CartQuantityForm({
            "quantity": item.quantity,
            "unit": item.unit,
        })

        if not form.is_valid():
            skipped_count += 1
            continue

        try:
            cart.add(
                product,
                form.cleaned_data["quantity"],
                form.cleaned_data["unit"],
            )
            added_count += 1

        except ValueError:
            skipped_count += 1

    if added_count:
        messages.success(
            request,
            "Товари з попередньої заявки додано до кошика."
        )
    else:
        messages.warning(
            request,
            "Не вдалося додати товари з попередньої заявки."
        )

    if skipped_count:
        messages.warning(
            request,
            f"Не додано позицій: {skipped_count}. "
            "Деякі товари більше недоступні або мають "
            "некоректну кількість."
        )

    return redirect("cart_detail")
