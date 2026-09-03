"""Modèle notifications — journal des SMS transactionnels (Issue #10).

Aucun envoi direct ici : le modèle trace chaque notification (audit,
diagnostic des échecs, anti-doublon des relances).
"""
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class SmsNotification(UUIDModel, TimeStampedModel):
    """Un SMS transactionnel lié à une commande (prêt, relance)."""

    class Kind(models.TextChoices):
        READY = "READY", "Linge prêt"
        REMINDER = "REMINDER", "Relance oubli"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SENT = "SENT", "Envoyé"
        SIMULATED = "SIMULATED", "Simulé (passerelle non configurée)"
        FAILED = "FAILED", "Échec"

    commande = models.ForeignKey(
        "orders.Commande",
        verbose_name="commande",
        on_delete=models.PROTECT,
        related_name="sms_notifications",
    )
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="sms_notifications",
    )
    kind = models.CharField("type", max_length=10, choices=Kind.choices)
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    phone_number = models.CharField("destinataire", max_length=32)
    message = models.TextField("message")
    provider_ref = models.CharField("référence passerelle", max_length=64, blank=True, default="")
    error_message = models.TextField("message d'erreur", blank=True, default="")

    class Meta:
        verbose_name = "notification SMS"
        verbose_name_plural = "notifications SMS"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_kind_display()}] {self.phone_number} — {self.status}"
