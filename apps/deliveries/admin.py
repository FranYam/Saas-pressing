from django.contrib import admin

from apps.deliveries.models import Courier


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "is_active", "pressing", "created_at")
    list_filter = ("is_active", "pressing")
    search_fields = ("name", "phone_number")
