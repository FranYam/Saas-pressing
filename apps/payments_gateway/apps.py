from django.apps import AppConfig


class PaymentsGatewayConfig(AppConfig):
    """Intégration fragile aux opérateurs (Orange Money / Moov Money) — Issue #9."""

    name = "apps.payments_gateway"
    label = "payments_gateway"
    verbose_name = "Passerelle Mobile Money"
