"""Sérialiseurs tenants : inscription d'un pressing et personnalisation visuelle."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.tenants.models import Pressing, HEX_COLOR_VALIDATOR

User = get_user_model()


class PressingSerializer(serializers.ModelSerializer):
    """Représentation d'un pressing — consommé par la PWA pour le theming
    (logo + couleurs appliqués aux variables CSS --primary-color / --secondary-color).
    """

    class Meta:
        model = Pressing
        fields = [
            "id",
            "name",
            "address",
            "phone",
            "owner_name",
            "logo",
            "primary_color",
            "secondary_color",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class GerantCreateSerializer(serializers.ModelSerializer):
    """Compte gérant créé simultanément au pressing lors de l'inscription."""

    password = serializers.CharField(
        write_only=True, validators=[validate_password], style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name"]
        extra_kwargs = {"first_name": {"required": False}, "last_name": {"required": False}}


class RegisterPressingSerializer(serializers.Serializer):
    """
    Inscription publique : crée le pressing ET son utilisateur gérant en
    une seule requête (voir tenants/services.register_pressing — transaction
    atomique : si le gérant est invalide, le pressing n'est pas créé).
    """

    name = serializers.CharField(max_length=255)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    owner_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    logo = serializers.ImageField(required=False)
    primary_color = serializers.CharField(
        max_length=7, required=False, default="#1E90FF", validators=[HEX_COLOR_VALIDATOR]
    )
    secondary_color = serializers.CharField(
        max_length=7, required=False, default="#FF8C00", validators=[HEX_COLOR_VALIDATOR]
    )
    gerant = GerantCreateSerializer()
