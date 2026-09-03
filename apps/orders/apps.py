from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Commandes & articles, cycle de vie, génération de tickets (Issues #6-#7)."""

    name = "apps.orders"
    label = "orders"
    verbose_name = "Commandes"
