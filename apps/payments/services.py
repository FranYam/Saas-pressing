"""Logique métier payments — règlements, soldes et créances (Issue #8)."""
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.clients.models import Client
from apps.core.exceptions import BusinessRuleError
from apps.orders.models import Commande
from apps.payments.models import Paiement

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Règlements
# ---------------------------------------------------------------------------

def get_commande_paid_amount(commande: Commande) -> Decimal:
    """Total déjà encaissé sur une commande."""
    paid = Paiement.objects.filter(commande=commande).aggregate(total=Sum("amount"))["total"]
    return paid or ZERO


@transaction.atomic
def register_paiement(*, commande: Commande, amount: Decimal, mode: str, date_paiement=None) -> Paiement:
    """
    Enregistre un règlement et met à jour le statut paiement de la commande.

    Règles (statut calculé côté serveur, jamais depuis le payload) :
    - mode CREDIT : montant 0, acte la mise à crédit (statut CREDIT, ou
      PARTIEL si un acompte existe déjà) ;
    - modes ESPECES / MOBILE_MONEY : montant positif, plafonné au reste à
      payer (pas de surpaiement) ;
    - statut PAYE interdit tout nouveau règlement.
    """
    if commande.payment_status == Commande.PaymentStatus.PAYE:
        raise BusinessRuleError("Cette commande est déjà entièrement payée.")

    paid = get_commande_paid_amount(commande)
    remaining = commande.total_price - paid

    if mode == Paiement.Mode.CREDIT:
        if amount != ZERO:
            raise BusinessRuleError(
                "Un enregistrement de crédit doit être créé avec un montant de 0."
            )
        new_status = (
            Commande.PaymentStatus.PARTIEL if paid > ZERO else Commande.PaymentStatus.CREDIT
        )
    else:
        if amount <= ZERO:
            raise BusinessRuleError("Le montant doit être positif pour ce mode de paiement.")
        if amount > remaining:
            raise BusinessRuleError(
                f"Le montant dépasse le reste à payer ({remaining} FCFA)."
            )
        new_status = (
            Commande.PaymentStatus.PAYE
            if amount == remaining
            else Commande.PaymentStatus.PARTIEL
        )

    paiement = Paiement.objects.create(
        commande=commande,
        amount=amount,
        mode=mode,
        date_paiement=date_paiement or timezone.now(),
        status=new_status,
        pressing=commande.pressing,
    )

    commande.payment_status = new_status
    commande.save(update_fields=["payment_status", "updated_at"])
    return paiement


# ---------------------------------------------------------------------------
# Soldes clients & créances
# ---------------------------------------------------------------------------

def get_client_balance(client: Client) -> dict:
    """
    Solde consolidé d'un client sur TOUTES ses commandes :
    total dû, total payé, reste (créance) + détail des commandes non soldées.
    """
    commandes = Commande.objects.filter(client=client).order_by("-date_depot")
    total_due = commandes.aggregate(total=Sum("total_price"))["total"] or ZERO
    total_paid = (
        Paiement.objects.filter(commande__client=client)
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    paid_by_commande = dict(
        Paiement.objects.filter(commande__client=client)
        .values_list("commande_id")
        .annotate(commande_total=Sum("amount"))
        .values_list("commande_id", "commande_total")
    )

    unpaid_commandes = [
        {
            "id": str(commande.id),
            "ticket_number": commande.ticket_number,
            "date_depot": commande.date_depot,
            "payment_status": commande.payment_status,
            "total_price": commande.total_price,
            "paid": paid_by_commande.get(commande.id, ZERO),
            "remaining": commande.total_price - paid_by_commande.get(commande.id, ZERO),
        }
        for commande in commandes
        if commande.payment_status != Commande.PaymentStatus.PAYE
    ]

    return {
        "client": str(client.id),
        "order_count": commandes.count(),
        "total_due": total_due,
        "total_paid": total_paid,
        "balance": total_due - total_paid,
        "unpaid_commandes": unpaid_commandes,
    }


def list_client_balances(pressing):
    """Clients du pressing annotés de leur solde (total_due, total_paid, balance)."""
    totals = (
        Commande.objects.filter(client=OuterRef("pk"))
        .values("client")
        .annotate(total=Sum("total_price"))
        .values("total")
    )
    paids = (
        Paiement.objects.filter(commande__client=OuterRef("pk"))
        .values("commande__client")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    return Client.objects.filter(pressing=pressing).annotate(
        total_due=Coalesce(Subquery(totals, output_field=DecimalField()), ZERO),
        total_paid=Coalesce(Subquery(paids, output_field=DecimalField()), ZERO),
        balance=F("total_due") - F("total_paid"),
    )


def list_debtors(pressing):
    """Clients du pressing ayant une créance (solde débiteur > 0)."""
    return list_client_balances(pressing).filter(balance__gt=ZERO)
