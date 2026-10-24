from django.contrib import admin

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

    def has_add_permission(self, request):
        return False