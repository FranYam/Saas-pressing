from django.contrib import admin

from apps.orders.models import Commande, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("ticket_number", "client", "status", "canal", "total_price", "date_depot")
    list_filter = ("status", "canal", "pressing")
    search_fields = ("ticket_number", "client__name", "client__phone_number")
    inlines = [OrderItemInline]
