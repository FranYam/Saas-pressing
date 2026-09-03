from django.contrib import admin

from apps.payments.models import Paiement


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("commande", "amount", "mode", "status", "date_paiement")
    list_filter = ("mode", "status", "pressing")
    search_fields = ("commande__ticket_number", "commande__client__name")
