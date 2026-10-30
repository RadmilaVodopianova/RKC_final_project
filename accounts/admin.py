from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.forms import (
    AdminPasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_display = (
        "username", "email", "first_name", "last_name", "access_status", "is_staff",
    )
    actions = (*BaseUserAdmin.actions, "approve_access")

    @admin.display(description="Доступ", ordering="is_active", boolean=True)
    def access_status(self, obj):
        return obj.is_active

    @admin.action(description="Схвалити доступ до сайту", permissions=["change"])
    def approve_access(self, request, queryset):
        approved = 0
        for user in queryset.filter(is_active=False):
            user.is_active = True
            user.save(update_fields=["is_active"])
            approved += 1
        self.message_user(request, f"Схвалено облікових записів: {approved}.")


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
