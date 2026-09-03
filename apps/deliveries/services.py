"""Logique métier deliveries — création de coursiers avec compte (Issue #11)."""
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.clients.services import clean_phone
from apps.core.exceptions import BusinessRuleError
from apps.deliveries.models import Courier

User = get_user_model()


@transaction.atomic
def create_courier(*, pressing, name: str, phone_number: str, password: str) -> Courier:
    """
    Crée le profil coursier ET son compte de connexion (rôle COURSIER)
    de manière atomique. Le téléphone sert d'identifiant (username),
    comme pour le reste de la plateforme.
    """
    phone = clean_phone(phone_number)

    if Courier.objects.filter(phone_number=phone, pressing=pressing).exists():
        raise BusinessRuleError("Ce numéro est déjà utilisé par un coursier de ce pressing.")
    if User.objects.filter(username=phone).exists():
        raise BusinessRuleError("Ce numéro est déjà utilisé comme identifiant.")

    courier = Courier.objects.create(
        name=name,
        phone_number=phone,
        pressing=pressing,
    )
    user = User.objects.create_user(
        username=phone,
        password=password,
        role=User.Role.COURSIER,
        pressing=pressing,
    )
    courier.user = user
    courier.save(update_fields=["user", "updated_at"])
    return courier


@transaction.atomic
def deactivate_courier(courier: Courier) -> None:
    """Désactive le profil et le compte — l'historique des livraisons reste traçable."""
    courier.is_active = False
    courier.save(update_fields=["is_active", "updated_at"])
    if courier.user is not None:
        courier.user.is_active = False
        courier.user.save(update_fields=["is_active"])
