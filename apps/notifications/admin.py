from django.contrib import admin

from apps.notifications.models import SmsNotification


@admin.register(SmsNotification)
class SmsNotificationAdmin(admin.ModelAdmin):
    list_display = ("kind", "phone_number", "status", "commande", "created_at")
    list_filter = ("kind", "status", "pressing")
    search_fields = ("phone_number", "message", "commande__ticket_number")
    readonly_fields = [f.name for f in SmsNotification._meta.fields]
