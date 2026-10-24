from django.contrib import admin
from .models import Category, ContactMessage, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "is_processed",
        "created_at",
    )

    list_filter = (
        "is_processed",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "message",
    )

    readonly_fields = (
        "name",
        "email",
        "phone",
        "message",
        "created_at",
    )

    fields = (
        "is_processed",
        "name",
        "email",
        "phone",
        "message",
        "created_at",
    )

    def has_add_permission(self, request):
        return False