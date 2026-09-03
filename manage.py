"""Utilitaire en ligne de commande Django (défaut : settings de développement)."""
import os
import sys


def main():
    """Exécute les tâches administratives Django."""
    # Développement par défaut. En production, DJANGO_SETTINGS_MODULE est
    # défini dans l'environnement (config.settings.prod).
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Vérifiez qu'il est installé et "
            "disponible sur votre variable d'environnement PYTHONPATH, et que "
            "vous avez activé votre environnement virtuel."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
