"""Sérialiseurs payments_gateway : initiation & suivi des demandes."""
from rest_framework import serializers

from apps.clients.services import clean_phone
from apps.payments_gateway.models import MobileMoneyRequest


class InitiateMobileMoneySerializer(serializers.Serializer):
    """Payload d'initiation : commande + téléphone payeur + opérateur."""

    commande = serializers.UUIDField()
    phone_number = serializers.CharField(max_length=32)
    operator = serializers.ChoiceField(choices=MobileMoneyRequest.Operator.choices)

    def validate_phone_number(self, value):
        return clean_phone(value)


class MobileMoneyRequestSerializer(serializers.ModelSerializer):
    """Représentation d'une demande Mobile Money (lecture)."""

    class Meta:
        model = MobileMoneyRequest
        fields = [
            "id",
            "commande",
            "operator",
            "phone_number",
            "amount",
            "status",
            "provider_ref",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
