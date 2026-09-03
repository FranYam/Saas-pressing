"""Logique métier tenants — orchestration hors des vues et sérialiseurs."""
from django.db import transaction

from apps.accounts.models import User
from apps.tenants.models import Pressing


@transaction.atomic
def register_pressing(*, pressing_data: dict, gerant_data: dict) -> tuple[Pressing, User]:
    """
    Crée atomiquement un pressing et le compte gérant associé.

    Si la création du gérant échoue (ex. numéro de téléphone déjà utilisé),
    le pressing créé juste avant est annulé par le rollback : aucune donnée
    orpheline ne reste en base.
    """
    pressing = Pressing.objects.create(**pressing_data)
    gerant = User.objects.create_user(
        username=gerant_data["username"],
        password=gerant_data["password"],
        first_name=gerant_data.get("first_name", ""),
        last_name=gerant_data.get("last_name", ""),
        role=User.Role.GERANT,
        pressing=pressing,
    )
    return pressing, gerant
