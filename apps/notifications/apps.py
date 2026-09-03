from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications SMS (statut PRET, relances 7 jours) — Issue #10."""

    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications SMS"
