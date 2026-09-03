"""Logique métier orders — tickets, cycle de vie, reçus (Issues #6-#7)."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.orders.models import Commande, OrderItem

# ---------------------------------------------------------------------------
# Tickets — format TX-YYMM-NNN, séquence remise à zéro chaque mois, par pressing
# ---------------------------------------------------------------------------

def generate_ticket_number(pressing, *, today=None) -> str:
    """
    Numéro de ticket court : « TX-2609-001 ».

    - Préfixe mensuel YYMM (réinitialisé chaque mois) ;
    - Séquence par pressing (unicité garantie par la contrainte
      unique_ticket_per_pressing) ;
    - select_for_update verrouille les tickets du mois pour éviter deux
      commandes simultanées avec le même numéro.

    Limite MVP : 999 commandes/mois/pressing (tri lexicographique).
    """
    today = today or timezone.localdate()
    prefix = f"TX-{today:%y%m}-"

    with transaction.atomic():
        last = (
            Commande.objects.select_for_update()
            .filter(pressing=pressing, ticket_number__startswith=prefix)
            .order_by("-ticket_number")
            .first()
        )
        next_seq = int(last.ticket_number[-3:]) + 1 if last else 1

    return f"{prefix}{next_seq:03d}"


# ---------------------------------------------------------------------------
# Cycle de vie — RECU → EN_TRAITEMENT → PRET → LIVRE
# ---------------------------------------------------------------------------

# RECU → PRET autorisé : les petits pressings marquent « prêt » sans passer
# par « en traitement ». En revanche, LIVRE exige strictement PRET.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Commande.Status.RECU: {Commande.Status.EN_TRAITEMENT, Commande.Status.PRET},
    Commande.Status.EN_TRAITEMENT: {Commande.Status.PRET},
    Commande.Status.PRET: {Commande.Status.LIVRE},
    Commande.Status.LIVRE: set(),  # terminal
}


@transaction.atomic
def update_commande_status(*, commande: Commande, new_status: str) -> Commande:
    """Fait progresser le statut d'une commande en validant la transition."""
    if new_status == commande.status:
        raise BusinessRuleError(
            f"La commande est déjà au statut {commande.get_status_display()}."
        )
    allowed = ALLOWED_TRANSITIONS.get(commande.status, set())
    if new_status not in allowed:
        raise BusinessRuleError(
            f"Transition interdite : {commande.get_status_display()} → {new_status}. "
            "Cycle attendu : Reçu → En traitement → Prêt → Livré."
        )

    commande.status = new_status
    if new_status == Commande.Status.PRET:
        commande.date_pret = timezone.now()  # cible des relances SMS (Issue #10)
    commande.save(update_fields=["status", "date_pret", "updated_at"])

    # Le signal post_save déclenche le SMS « prêt » (apps/notifications/signals.py).
    return commande


# ---------------------------------------------------------------------------
# Reçu client — texte brut prêt pour impression thermique 58/80mm ou SMS
# ---------------------------------------------------------------------------

def format_receipt(commande: Commande) -> str:
    """Reçu texte : nom du pressing, ticket, dates, articles, total FCFA."""
    width = 32
    separator = "-" * width
    lines = [
        commande.pressing.name[:width],
        commande.pressing.phone[:width],
        separator,
        f"Ticket  : {commande.ticket_number}",
        f"Client  : {commande.client.name}",
        f"Depot   : {timezone.localtime(commande.date_depot):%d/%m/%Y %H:%M}",
        f"Retrait : {timezone.localtime(commande.date_retrait_prevue):%d/%m/%Y %H:%M}",
        separator,
    ]
    for item in commande.articles.all():
        lines.append(f"{item.quantity} x {item.clothing_type}".ljust(22)[:22] + f"{item.unit_price:>10}")
    lines += [separator, f"TOTAL : {commande.total_price} FCFA"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Création transactionnelle (Issue #6)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_commande(
    *,
    pressing,
    client,
    articles: list[dict],
    date_retrait_prevue,
    canal: str = Commande.Canal.COMPTOIR,
    date_depot=None,
) -> Commande:
    """
    Crée une commande ET ses articles de manière atomique.

    - Ticket court généré automatiquement (critère Issue #7) ;
    - Le total est calculé côté serveur depuis les articles (jamais depuis
      le payload client) ;
    - Si un article échoue à l'insertion, la commande créée juste avant est
      annulée par le rollback (critère d'acceptation Issue #6).
    """
    total = sum(
        (Decimal(article["quantity"]) * article["unit_price"] for article in articles),
        Decimal("0.00"),
    )

    commande = Commande.objects.create(
        pressing=pressing,
        client=client,
        ticket_number=generate_ticket_number(pressing),
        canal=canal,
        date_depot=date_depot or timezone.now(),
        date_retrait_prevue=date_retrait_prevue,
        total_price=total,
    )

    OrderItem.objects.bulk_create(
        [OrderItem(commande=commande, **article) for article in articles]
    )

    return commande
