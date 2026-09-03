from django.contrib import admin

from apps.payments_gateway.models import MobileMoneyRequest


@admin.register(MobileMoneyRequest)
class MobileMoneyRequestAdmin(admin.ModelAdmin):
    list_display = ("commande", "operator", "phone_number", "amount", "status", "created_at")
    list_filter = ("operator", "status", "pressing")
    search_fields = ("provider_ref", "commande__ticket_number", "phone_number")
