"""Modèles orders — Commande et ses articles (cœur métier, Issues #6-#7)."""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Commande(UUIDModel, TimeStampedModel):
    """
    Commande déposée par un client d'un pressing.

    Cycle de vie (transitions contrôlées à l'Issue #7) :
    RECU → EN_TRAITEMENT → PRET → LIVRE.

    `ticket_number` est généré à la création par orders/services.py
    (Issue #7) — nullable tant que le générateur n'est pas branché.

    Champs logistiques (adresse_collecte, statut_livraison, coursier) :
    ajoutés à l'Issue #11.
    """

    class Status(models.TextChoices):
        RECU = "RECU", "Reçu"
        EN_TRAITEMENT = "EN_TRAITEMENT", "En traitement"
        PRET = "PRET", "Prêt"
        LIVRE = "LIVRE", "Livré"

    class Canal(models.TextChoices):
        COMPTOIR = "COMPTOIR", "Comptoir"
        EN_LIGNE = "EN_LIGNE", "En ligne"

    class PaymentStatus(models.TextChoices):
        """Statut du règlement — mis à jour à chaque paiement (Issue #8)."""

        PAYE = "PAYE", "Payé"
        PARTIEL = "PARTIEL", "Partiel"
        CREDIT = "CREDIT", "Crédit"

    client = models.ForeignKey(
        "clients.Client",
        verbose_name="client",
        on_delete=models.PROTECT,  # jamais de suppression d'un client avec commandes
        related_name="commandes",
    )
    pressing = models.ForeignKey(
        "tenants.Pressing",
        verbose_name="pressing",
        on_delete=models.CASCADE,
        related_name="commandes",
    )
    ticket_number = models.CharField(
        "n° ticket", max_length=20, null=True, blank=True
    )
    status = models.CharField(
        "statut", max_length=20, choices=Status.choices, default=Status.RECU
    )
    payment_status = models.CharField(
        "statut paiement",
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CREDIT,  # impayé tant qu'aucun règlement n'est enregistré
    )
    canal = models.CharField(
        "canal", max_length=10, choices=Canal.choices, default=Canal.COMPTOIR
    )
    date_depot = models.DateTimeField("date de dépôt")
    date_retrait_prevue = models.DateTimeField("date de retrait prévue")
    # Renseigné au passage PRET (orders/services) — cible des relances > 7 jours.
    date_pret = models.DateTimeField("passé prêt le", null=True, blank=True)
    total_price = models.DecimalField(
        "montant total", max_digits=10, decimal_places=2, default=0
    )

    class Meta:
        verbose_name = "commande"
        ordering = ["-date_depot"]
        constraints = [
            # Ticket unique au sein du pressing : chaque pressing a SA
            # numérotation (le client présente son ticket au bon établissement).
            models.UniqueConstraint(
                fields=["pressing", "ticket_number"],
                name="unique_ticket_per_pressing",
            ),
        ]

    def __str__(self):
        return f"{self.ticket_number or self.id.hex[:8]} — {self.client}"


class OrderItem(UUIDModel, TimeStampedModel):
    """Article d'une commande (ex. 2 × Chemise) — prix fixés au dépôt."""

    commande = models.ForeignKey(
        Commande, verbose_name="commande", on_delete=models.CASCADE, related_name="articles"
    )
    clothing_type = models.CharField("type de vêtement", max_length=100)
    quantity = models.PositiveIntegerField(
        "quantité", default=1, validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        "prix unitaire",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "article de commande"
        verbose_name_plural = "articles de commande"

    def __str__(self):
        return f"{self.quantity} × {self.clothing_type}"
