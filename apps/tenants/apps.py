from django.apps import AppConfig


class TenantsConfig(AppConfig):
    """Gestion des établissements (tenants) et de leur personnalisation visuelle."""

    name = "apps.tenants"
    label = "tenants"
    verbose_name = "Établissements"
