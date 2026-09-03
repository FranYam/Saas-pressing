from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Tableau de bord gérant — lecture pure, aucun modèle."""

    name = "apps.dashboard"
    label = "dashboard"
    verbose_name = "Tableau de bord"
