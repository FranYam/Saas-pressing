"""Modèle Tarif — catalogue de prix propre à chaque pressing."""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Tarif(UUIDModel, TimeStampedModel):
    """Une ligne du catalogue (ex. Chemise — 500 FCFA).

    Les prix servis au portail client et utilisés pour chiffrer les
    demandes de collecte en ligne : le montant est TOUJOURS repris depuis
    cette table côté serveur, jamais depuis le payload client.
    """

    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="tarifs",
    )
    name = models.CharField("article", max_length=100)
    category = models.CharField("catégorie", max_length=100, blank=True, default="")
    price = models.DecimalField(
        "prix (FCFA)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "tarif"
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["pressing", "name"],
                condition=models.Q(is_active=True),
                name="unique_active_tarif_name_per_pressing",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.price} FCFA"


# Tarifs standard proposés à la création d'un pressing (marché burkinabè).
DEFAULT_TARIFS: list[tuple[str, str, str]] = [
    ("Chemise", "Vêtements", "500"),
    ("Pantalon", "Vêtements", "750"),
    ("Robe", "Vêtements", "1000"),
    ("Costume", "Vêtements", "3000"),
    ("Boubou", "Traditionnel", "2000"),
    ("Drap", "Linge de maison", "1500"),
    ("Rideau", "Linge de maison", "2000"),
]
