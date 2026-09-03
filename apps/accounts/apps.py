from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Gestion des utilisateurs (gérant / employé) rattachés à un pressing."""

    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Comptes & rôles"
