from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications SMS (statut PRET, relances) — Issue #10."""

    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications SMS"

    def ready(self):
        # Enregistre les signaux post_save/pre_save sur Commande.
        from apps.notifications import signals  # noqa: F401
