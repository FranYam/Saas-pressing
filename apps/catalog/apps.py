from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Catalogue de tarifs du pressing — visible par les clients du portail."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    verbose_name = "Catalogue"

    def ready(self):
        # Le signal seed les tarifs standard à la création d'un pressing.
        from apps.catalog import signals  # noqa: F401
