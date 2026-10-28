from django.contrib import admin, messages
from django.db import transaction

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

    fields = (
        "product",
        "product_name",
        "quantity",
        "unit",
    )

    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "phone",
        "status",
        "created_at",
    )

    list_filter = ("status", "created_at")

    search_fields = (
        "=id",
        "full_name",
        "email",
        "phone",
    )

    readonly_fields = (
        "user",
        "full_name",
        "email",
        "phone",
        "comment",
        "created_at",
        "updated_at",
    )

    fields = (
        "status",
        "user",
        "full_name",
        "email",
        "phone",
        "comment",
        "created_at",
        "updated_at",
    )

    inlines = [OrderItemInline]

    actions = (
        "mark_processing",
        "mark_confirmed",
        "mark_cancelled",
    )

    def _set_status(self, request, queryset, status):
        updated_count = 0

        with transaction.atomic():
            for order in queryset.select_for_update().order_by("pk"):
                if order.status == status:
                    continue

                order.status = status
                order.save(update_fields=["status", "updated_at"])
                updated_count += 1

        self.message_user(
            request,
            f"Оновлено заявок: {updated_count}.",
            level=messages.SUCCESS,
        )

    @admin.action(description="В обробці", permissions=["change"])
    def mark_processing(self, request, queryset):
        self._set_status(request, queryset, Order.Status.PROCESSING)

    @admin.action(description="Погодити", permissions=["change"])
    def mark_confirmed(self, request, queryset):
        self._set_status(request, queryset, Order.Status.CONFIRMED)

    @admin.action(description="Скасувати", permissions=["change"])
    def mark_cancelled(self, request, queryset):
        self._set_status(request, queryset, Order.Status.CANCELLED)

    def has_add_permission(self, request):
        return False