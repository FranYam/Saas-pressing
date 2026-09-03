"""Modèle Paiement — règlements et créances (Issue #8).

Les enregistrements de paiement sont immuables : pas d'édition ni de
suppression (une erreur de saisie se corrige par une écriture inverse
ultérieure — piste d'audit financière).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


class Paiement(UUIDModel, TimeStampedModel):
    """
    Un règlement enregistré sur une commande.

    - `amount` = argent réellement encaissé dans cette opération
      (0 pour un simple enregistrement « mis à crédit ») ;
    - `status` = statut résultant pour la commande, CALCULÉ côté serveur
      par payments/services.register_paiement — jamais depuis le payload ;
    - `pressing` est dénormalisé depuis la commande pour le scoping tenant.
    """

    class Mode(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        CREDIT = "CREDIT", "Crédit"

    class Status(models.TextChoices):
        PAYE = "PAYE", "Payé"
        PARTIEL = "PARTIEL", "Partiel"
        CREDIT = "CREDIT", "Crédit"

    commande = models.ForeignKey(
        "orders.Commande",
        verbose_name="commande",
        on_delete=models.PROTECT,  # historique financier indestructible
        related_name="paiements",
    )
    amount = models.DecimalField(
        "montant encaissé",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    mode = models.CharField("mode", max_length=15, choices=Mode.choices, default=Mode.ESPECES)
    date_paiement = models.DateTimeField("date de paiement", default=timezone.now)
    status = models.CharField("statut", max_length=10, choices=Status.choices)
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="paiements",
    )

    class Meta:
        verbose_name = "paiement"
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"{self.amount} FCFA — {self.commande}"
