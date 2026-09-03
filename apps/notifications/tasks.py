"""Tâches d'envoi SMS (Issue #10) — prêtes pour Celery + Redis.

Aujourd'hui les fonctions s'exécutent de façon synchrone (pas de broker).
Branchement futur SANS rien réécrire ailleurs :

    from celery import shared_task

    @shared_task
    def send_sms_task(notification_id): ...

puis remplacer dans apps/notifications/signals.py l'appel direct
`send_sms_task(...)` par `send_sms_task.delay(...)` (idem pour les relances
dans la commande de management, planifiée ensuite via celery-beat).
"""
from datetime import timedelta

from django.utils import timezone

from apps.notifications.models import SmsNotification
from apps.notifications.services import (
    build_ready_message,
    build_reminder_message,
    create_notification,
    send_notification,
)
from apps.orders.models import Commande

REMINDER_DELAY = timedelta(days=7)


def send_sms_task(notification_id):
    """Envoie une notification en tâche de fond (idempotente)."""
    notification = SmsNotification.objects.filter(pk=notification_id).first()
    if notification is None or notification.status != SmsNotification.Status.PENDING:
        return  # déjà traitée ou introuvable
    send_notification(notification)


def dispatch_ready_notification(commande: Commande) -> SmsNotification:
    """Crée et envoie le SMS « linge prêt » (déclenché par le signal)."""
    notification = create_notification(
        commande=commande,
        kind=SmsNotification.Kind.READY,
        message=build_ready_message(commande),
    )
    send_sms_task(str(notification.id))
    return notification


def send_reminders_task() -> int:
    """
    Relance les clients dont le linge est PRET non retiré depuis plus de
    7 jours (date_pret). Une commande déjà relancée n'est pas re-relancée
    (anti-spam) — appelée par la commande de management, à planifier en cron.
    """
    cutoff = timezone.now() - REMINDER_DELAY

    already_reminded = SmsNotification.objects.filter(
        kind=SmsNotification.Kind.REMINDER
    ).values_list("commande_id", flat=True)

    commandes = (
        Commande.objects.filter(
            status=Commande.Status.PRET,
            date_pret__isnull=False,
            date_pret__lt=cutoff,
        )
        .exclude(id__in=already_reminded)
        .select_related("client", "pressing")
    )

    count = 0
    for commande in commandes:
        notification = create_notification(
            commande=commande,
            kind=SmsNotification.Kind.REMINDER,
            message=build_reminder_message(commande),
        )
        send_sms_task(str(notification.id))
        count += 1
    return count
