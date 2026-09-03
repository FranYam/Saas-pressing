from django.contrib import admin

from apps.clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "pressing", "created_at")
    search_fields = ("name", "phone_number")
    list_filter = ("pressing",)
