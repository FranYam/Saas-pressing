"""Modèle deliveries — coursiers du pressing (Issue #11)."""
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Courier(UUIDModel, TimeStampedModel):
    """
    Un coursier (livreur) rattaché à un pressing.

    `user` (rôle COURSIER) est le compte de connexion du coursier : créé
    en même temps que le profil par deliveries/services.create_courier.
    Unicité du téléphone au sein du pressing (comme pour les clients).
    """

    name = models.CharField("nom", max_length=255)
    phone_number = models.CharField("téléphone", max_length=32)
    is_active = models.BooleanField("actif", default=True)
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="couriers",
    )
    user = models.OneToOneField(
        "accounts.User",
        verbose_name="compte de connexion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="courier_profile",
    )

    class Meta:
        verbose_name = "coursier"
        verbose_name_plural = "coursiers"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["phone_number", "pressing"],
                name="unique_courier_phone_per_pressing",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone_number})"
