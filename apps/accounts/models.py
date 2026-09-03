"""Utilisateur personnalisé : identifié par son numéro de téléphone (username),
rattaché à un pressing, avec un rôle (gérant / employé).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class User(UUIDModel, TimeStampedModel, AbstractUser):
    """
    Utilisateur de la plateforme : gérant ou employé d'un pressing.

    Le `username` contient le numéro de téléphone — identifiant unique,
    adapté à l'usage mobile-first du marché local.

    `pressing` est null uniquement pour les super-admins de la plateforme
    (is_superuser), qui ne sont pas rattachés à un établissement.
    """

    class Role(models.TextChoices):
        GERANT = "GERANT", "Gérant"
        EMPLOYE = "EMPLOYE", "Employé"
        COURSIER = "COURSIER", "Coursier"

    role = models.CharField(
        "rôle",
        max_length=16,
        choices=Role.choices,
        default=Role.EMPLOYE,  # moindre privilège par défaut
    )
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="users",
    )

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_gerant(self) -> bool:
        return self.role == self.Role.GERANT
