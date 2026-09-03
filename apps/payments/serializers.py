"""Sérialiseur payments : enregistrement de règlements au comptoir."""
from rest_framework import serializers

from apps.clients.serializers import ClientSerializer
from apps.payments.models import Paiement
from apps.payments.services import register_paiement


class PaiementSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    date_paiement = serializers.DateTimeField(required=False)

    class Meta:
        model = Paiement
        fields = [
            "id",
            "commande",
            "amount",
            "mode",
            "date_paiement",
            "status",
            "pressing",
            "created_at",
        ]
        read_only_fields = ["id", "status", "pressing", "created_at"]

    def validate(self, attrs):
        # Isolation : impossible d'encaisser sur une commande d'un autre pressing.
        commande = attrs.get("commande")
        request = self.context.get("request")
        pressing = getattr(getattr(request, "user", None), "pressing", None)
        if commande and pressing and commande.pressing_id != pressing.id:
            raise serializers.ValidationError(
                {"commande": "Cette commande n'appartient pas à votre pressing."}
            )
        return attrs

    def create(self, validated_data):
        # Le statut est calculé par le service, jamais depuis le payload.
        return register_paiement(
            commande=validated_data["commande"],
            amount=validated_data["amount"],
            mode=validated_data.get("mode", Paiement.Mode.ESPECES),
            date_paiement=validated_data.get("date_paiement"),
        )


class ClientBalanceSerializer(serializers.Serializer):
    """Ligne du relevé des créances (endpoint debtors — gérant)."""

    # source="*" : l'objet annoté EST le client, on le représente tel quel.
    client = ClientSerializer(source="*", read_only=True)
    total_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
