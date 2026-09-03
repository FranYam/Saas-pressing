from django.contrib import admin

from apps.tenants.models import Pressing


@admin.register(Pressing)
class PressingAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "owner_name", "primary_color", "secondary_color", "created_at")
    search_fields = ("name", "phone", "owner_name")
