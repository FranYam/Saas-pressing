"""Seed automatique du catalogue standard à la création d'un pressing."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.catalog.models import DEFAULT_TARIFS, Tarif
from apps.tenants.models import Pressing


@receiver(post_save, sender=Pressing)
def seed_default_catalog(sender, instance: Pressing, created: bool, **kwargs):
    """Un pressing naît avec les tarifs standard — modifiables ensuite."""
    if not created:
        return
    Tarif.objects.bulk_create(
        [
            Tarif(pressing=instance, name=name, category=category, price=price)
            for name, category, price in DEFAULT_TARIFS
        ]
    )
