"""Modèle Pressing — l'établissement, racine de toute donnée métier."""
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message="Le champ doit être un code couleur hexadécimal (ex. #1E90FF).",
)


class Pressing(UUIDModel, TimeStampedModel):
    """
    Un établissement de pressing (tenant).

    La couleur primaire/secondaire et le logo sont consommés par la PWA via
    GET /api/v1/tenants/profile/ (Issue #3) pour habiller dynamiquement
    l'interface par pressing.
    """

    name = models.CharField("nom", max_length=255)
    address = models.TextField("adresse", blank=True)
    phone = models.CharField("téléphone", max_length=32, blank=True)
    owner_name = models.CharField("propriétaire", max_length=255, blank=True)
    logo = models.ImageField("logo", upload_to="tenants/logos/", blank=True)
    primary_color = models.CharField(
        "couleur primaire",
        max_length=7,
        default="#1E90FF",
        validators=[HEX_COLOR_VALIDATOR],
    )
    secondary_color = models.CharField(
        "couleur secondaire",
        max_length=7,
        default="#FF8C00",
        validators=[HEX_COLOR_VALIDATOR],
    )

    class Meta:
        verbose_name = "pressing"
        verbose_name_plural = "pressings"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
