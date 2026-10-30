from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import Product

from .cart import Cart
from .context_processors import cart_counter
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
    errors = []

    if form.is_valid():
        try:
            Cart(request).add(
                product,
                form.cleaned_data["quantity"],
                form.cleaned_data["unit"],
            )
        except ValueError as error:
            errors.append(str(error))
    else:
        errors = [str(error) for field_errors in form.errors.values() for error in field_errors]

    if "application/json" in request.headers.get("Accept", "").lower():
        return JsonResponse(
            {
                "ok": not errors,
                "message": "Товар додано до кошика." if not errors else " ".join(errors),
                "cart_count": cart_counter(request)["cart_item_count"],
            },
            status=400 if errors else 200,
        )

    if errors:
        for error in errors:
            messages.error(request, error)
    else:
        messages.success(request, "Товар додано до кошика.")

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


def _send_order_created_email(order_id):
    order = Order.objects.prefetch_related("items").get(pk=order_id)
    lines = [
        f"Отримано нову заявку №{order.customer_number}.",
        f"Внутрішній ID заявки: {order.pk}",
        f"Клієнт: {order.full_name}",
        f"Електронна пошта: {order.email}",
        f"Телефон: {order.phone}",
        f"Статус: {order.get_status_display()}",
        "",
        "Товари у заявці:",
    ]
    for item in order.items.all():
        quantity = format(item.quantity, ".0f" if item.unit == "pcs" else ".2f")
        quantity = quantity.replace(".", ",")
        lines.append(f"- {item.product_name} — {quantity} {item.get_unit_display()}")
    if order.comment:
        lines.extend(["", "Коментар клієнта:", order.comment])

    EmailMessage(
        subject=f"Нова заявка №{order.customer_number} (ID {order.pk})",
        body="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.MANAGER_EMAIL],
        reply_to=[order.email],
    ).send(using="default")


def _build_customer_order_created_email(order, order_url):
    lines = [
        f"Вітаємо, {order.full_name}!",
        "",
        f"Дякуємо! Вашу заявку №{order.customer_number} створено та отримано.",
        f"Статус під час створення: {order.get_status_display()}.",
        "Менеджер перевірить наявність продукції та зв’яжеться з вами,",
        "щоб погодити вартість, строки виготовлення й умови отримання.",
        "",
        "Товари у заявці:",
    ]
    for item in order.items.all():
        quantity = format(item.quantity, ".0f" if item.unit == "pcs" else ".2f")
        quantity = quantity.replace(".", ",")
        lines.append(f"- {item.product_name} — {quantity} {item.get_unit_display()}")
    if order.comment:
        lines.extend(["", "Ваш коментар:", order.comment])
    lines.extend([
        "",
        "Переглянути заявку в особистому кабінеті:",
        order_url,
        "",
        f"Для зв’язку з менеджером: {settings.MANAGER_EMAIL}",
        "Роздільнянський ковбасний цех",
    ])
    return EmailMessage(
        subject=f"Вашу заявку №{order.customer_number} створено",
        body="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
        reply_to=[settings.MANAGER_EMAIL],
    )


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

                order_url = request.build_absolute_uri(
                    reverse("order_detail", kwargs={"pk": order.pk})
                )
                customer_message = _build_customer_order_created_email(order, order_url)

                transaction.on_commit(
                    lambda order_id=order.pk: _send_order_created_email(order_id),
                    robust=True,
                )
                transaction.on_commit(
                    lambda message=customer_message: message.send(using="default"),
                    robust=True,
                )

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

@login_required
@require_POST
def order_cancel(request, pk):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=pk,
            user=request.user,
        )
        if order.status != Order.Status.NEW:
            messages.error(
                request,
                "Скасувати можна лише заявку зі статусом «Нова».",
            )
        else:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Заявку №{order.customer_number} скасовано.")

    return redirect("order_detail", pk=order.pk)


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
