"""Relance SMS des linges prêts non retirés depuis plus de 7 jours.

Usage : python manage.py send_reminders
À planifier en cron (ou celery-beat une fois le broker branché) :
    0 9 * * *  → une relance par commande, anti-doublon intégré.
"""
from django.core.management.base import BaseCommand

from apps.notifications.tasks import send_reminders_task


class Command(BaseCommand):
    help = "Envoie une relance SMS aux clients dont le linge est prêt depuis plus de 7 jours."

    def handle(self, *args, **options):
        sent = send_reminders_task()
        self.stdout.write(
            self.style.SUCCESS(f"{sent} relance(s) SMS traitée(s).")
        )
