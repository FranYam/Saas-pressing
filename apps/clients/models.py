"""Modèle Client — répertoire propre à chaque pressing (Issue #5)."""
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Client(UUIDModel, TimeStampedModel):
    """
    Client final d'un pressing.

    Le numéro est stocké normalisé (chiffres uniquement, ex. 70123456) —
    voir clients/services.normalize_phone. La contrainte unique
    (phone_number, pressing) garantit l'unicité au sein d'un même pressing
    et SON index intégré (colonne de gauche phone_number) sert la recherche
    par préfixe au comptoir — pas besoin d'un index séparé.
    """

    name = models.CharField("nom", max_length=255)
    phone_number = models.CharField("téléphone", max_length=32)
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="clients",
    )

    class Meta:
        verbose_name = "client"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["phone_number", "pressing"],
                name="unique_client_phone_per_pressing",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone_number})"
