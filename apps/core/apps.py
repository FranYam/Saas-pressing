from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Fondations partagées — aucun modèle métier ici."""

    name = "apps.core"
    label = "core"
    verbose_name = "Core"
