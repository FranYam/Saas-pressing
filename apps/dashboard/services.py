"""Agrégations du tableau de bord gérant (Issue #12).

Tout est scopé par pressing (isolation multi-tenant) et calculé en SQL
via Sum/Count — consolidé en temps réel à chaque appel.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.orders.models import Commande
from apps.payments.models import Paiement
from apps.payments.services import list_debtors

ZERO = Decimal("0.00")

# Linge prêt non retiré depuis plus de 7 jours (même seuil que les relances).
UNCLAIMED_DELAY = timedelta(days=7)
UNCLAIMED_LIMIT = 20


def get_summary(pressing, *, now=None) -> dict:
    """Compile les indicateurs du jour pour un pressing."""
    now = now or timezone.now()
    today = now.date()

    paiements = Paiement.objects.filter(pressing=pressing)
    commandes = Commande.objects.filter(pressing=pressing)

    # --- Financier (consolidé depuis TOUS les paiements enregistrés) ---
    revenue_today = (
        paiements.filter(date_paiement__date=today).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    revenue_month = (
        paiements.filter(
            date_paiement__year=today.year, date_paiement__month=today.month
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    total_due = commandes.aggregate(total=Sum("total_price"))["total"] or ZERO
    total_paid = paiements.aggregate(total=Sum("amount"))["total"] or ZERO
    outstanding_debts = total_due - total_paid

    debtors_count = list_debtors(pressing).count()

    # --- Opérationnel ---
    orders_today = commandes.filter(date_depot__date=today).count()
    orders_in_progress = commandes.exclude(status=Commande.Status.LIVRE).count()
    orders_ready = commandes.filter(status=Commande.Status.PRET).count()

    # --- Linge non réclamé (prêt depuis plus de 7 jours) ---
    cutoff = now - UNCLAIMED_DELAY
    unclaimed_query = (
        commandes.filter(status=Commande.Status.PRET, date_pret__lt=cutoff)
        .select_related("client")
        .order_by("date_pret")[:UNCLAIMED_LIMIT]
    )
    unclaimed = [
        {
            "id": str(commande.id),
            "ticket_number": commande.ticket_number,
            "client_name": commande.client.name,
            "client_phone": commande.client.phone_number,
            "ready_since": commande.date_pret,
            "days_waiting": (now - commande.date_pret).days,
        }
        for commande in unclaimed_query
    ]

    return {
        "date": today,
        "revenue_today": revenue_today,
        "revenue_month": revenue_month,
        "orders_today": orders_today,
        "orders_in_progress": orders_in_progress,
        "orders_ready": orders_ready,
        "outstanding_debts": outstanding_debts,
        "debtors_count": debtors_count,
        "unclaimed": unclaimed,
    }
