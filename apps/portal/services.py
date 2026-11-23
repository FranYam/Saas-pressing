"""Business operations for the public client portal."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Tarif
from apps.clients.models import Client
from apps.orders.models import Commande
from apps.orders.services import create_commande


@transaction.atomic
def create_collection_order(
    *, client: Client, address: str, slot: str, notes: str, items: list[dict]
):
    """Create a home collection using current prices from this client's catalog."""
    tariffs = {
        tariff.name: tariff
        for tariff in Tarif.objects.filter(pressing=client.pressing, is_active=True)
    }
    priced_items = []
    for item in items:
        name = item["clothing_type"].strip()
        tariff = tariffs.get(name)
        if tariff is None:
            raise ValidationError({"articles": f"{name} n'est pas au catalogue."})
        priced_items.append(
            {
                "clothing_type": tariff.name,
                "quantity": item["quantity"],
                "unit_price": tariff.price,
            }
        )

    address_parts = [address]
    if slot:
        address_parts.append(f"Créneau : {slot}")
    if notes:
        address_parts.append(f"Note : {notes}")

    commande = create_commande(
        pressing=client.pressing,
        client=client,
        articles=priced_items,
        date_retrait_prevue=timezone.now() + timedelta(days=3),
        canal=Commande.Canal.EN_LIGNE,
    )
    commande.delivery_status = Commande.DeliveryStatus.A_COLLECTER
    commande.collect_address = " — ".join(address_parts)
    commande.save(update_fields=["delivery_status", "collect_address", "updated_at"])
    return commande
