from django.apps import AppConfig


class DeliveriesConfig(AppConfig):
    """Coursiers & assignation aux commandes de livraison (Issue #11)."""

    name = "apps.deliveries"
    label = "deliveries"
    verbose_name = "Livraisons"
