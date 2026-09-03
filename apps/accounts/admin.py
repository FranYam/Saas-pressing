from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "role", "pressing", "is_active", "created_at")
    list_filter = ("role", "is_active", "pressing")
    search_fields = ("username",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Pressing & rôle", {"fields": ("pressing", "role")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Pressing & rôle", {"fields": ("pressing", "role")}),
    )
