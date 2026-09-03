"""Modèle payments_gateway — suivi des demandes Mobile Money (Issue #9).

Cette app ne porte AUCUNE logique financière : les écritures de paiement
restent dans `payments/`. Elle suit uniquement les allers-retours avec les
opérateurs (fragiles, externes) et sert de point d'ancrage idempotent aux
webhooks.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class MobileMoneyRequest(UUIDModel, TimeStampedModel):
    """Une demande de push USSD/STK envoyée à un opérateur."""

    class Operator(models.TextChoices):
        ORANGE = "ORANGE", "Orange Money"
        MOOV = "MOOV", "Moov Money"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        CONFIRMED = "CONFIRMED", "Confirmée"
        FAILED = "FAILED", "Échouée"
        CANCELLED = "CANCELLED", "Annulée"

    commande = models.ForeignKey(
        "orders.Commande",
        verbose_name="commande",
        on_delete=models.PROTECT,
        related_name="mobile_money_requests",
    )
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="mobile_money_requests",
    )
    operator = models.CharField("opérateur", max_length=10, choices=Operator.choices)
    phone_number = models.CharField("téléphone payeur", max_length=32)
    amount = models.DecimalField(
        "montant demandé",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    provider_ref = models.CharField(
        "référence opérateur", max_length=64, blank=True, default=""
    )
    error_message = models.TextField("message d'erreur", blank=True, default="")

    class Meta:
        verbose_name = "demande Mobile Money"
        verbose_name_plural = "demandes Mobile Money"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_operator_display()} {self.amount} FCFA — {self.status}"
