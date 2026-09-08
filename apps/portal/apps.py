from django.apps import AppConfig


class PortalConfig(AppConfig):
    """Portail client public — accès aux commandes par ticket + téléphone."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.portal"
    verbose_name = "Portail client"
