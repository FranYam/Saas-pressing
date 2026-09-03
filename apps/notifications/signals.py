"""Signal Django : passage d'une commande au statut PRET → SMS (Issue #10).

`post_save` ne connaît pas l'ancienne valeur : un receiver `pre_save`
capture le statut précédent sur l'instance, puis `post_save` déclenche
uniquement sur la TRANSITION vers PRET (jamais sur un simple re-save).
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.orders.models import Commande

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Commande)
def capture_previous_status(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            Commande.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
    else:
        instance._previous_status = None


@receiver(post_save, sender=Commande)
def notify_client_when_ready(sender, instance, created, **kwargs):
    previous = getattr(instance, "_previous_status", None)
    if instance.status != Commande.Status.PRET or previous == Commande.Status.PRET:
        return

    try:
        from apps.notifications.tasks import dispatch_ready_notification

        dispatch_ready_notification(instance)
    except Exception:  # noqa: BLE001 — jamais bloquer l'action métier
        logger.exception("Échec de la notification SMS pour la commande %s", instance.pk)
