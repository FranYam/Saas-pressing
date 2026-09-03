from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Paiements (espèces, crédit, mobile money) & calcul des créances (Issue #8)."""

    name = "apps.payments"
    label = "payments"
    verbose_name = "Paiements"
