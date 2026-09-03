"""Modèles abstraits partagés par toutes les apps métier."""
import uuid

from django.db import models


class UUIDModel(models.Model):
    """Clé primaire UUID partagée par toutes les entités métier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Horodatage automatique création / modification."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
