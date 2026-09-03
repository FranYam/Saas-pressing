"""Sérialiseur orders : articles imbriqués en lecture ET en écriture."""
from rest_framework import serializers

from apps.orders.models import Commande, OrderItem
from apps.orders.services import create_commande, format_receipt


class OrderItemSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)

    class Meta:
        model = OrderItem
        fields = ["id", "clothing_type", "quantity", "unit_price"]
        read_only_fields = ["id"]


class CommandeSerializer(serializers.ModelSerializer):
    articles = OrderItemSerializer(many=True)
    receipt = serializers.SerializerMethodField()
    assigned_courier_name = serializers.SerializerMethodField()

    class Meta:
        model = Commande
        fields = [
            "id",
            "ticket_number",
            "client",
            "status",
            "payment_status",
            "canal",
            "date_depot",
            "date_retrait_prevue",
            "total_price",
            "collect_address",
            "delivery_status",
            "assigned_courier",
            "assigned_courier_name",
            "articles",
            "receipt",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "status",
            "payment_status",
            "date_depot",
            "total_price",
            "assigned_courier",
            "assigned_courier_name",
            "created_at",
        ]

    def get_receipt(self, obj) -> str:
        """Reçu texte prêt pour impression thermique ou partage SMS/WhatsApp."""
        return format_receipt(obj)

    def get_assigned_courier_name(self, obj) -> str | None:
        return obj.assigned_courier.name if obj.assigned_courier else None

    def validate(self, attrs):
        articles = attrs.get("articles")
        if not articles:
            raise serializers.ValidationError(
                {"articles": "Au moins un article est requis."}
            )

        # Une commande avec collecte à domicile démarre le cycle logistique.
        collect_address = attrs.get("collect_address", "")
        if collect_address and not attrs.get("delivery_status"):
            attrs["delivery_status"] = Commande.DeliveryStatus.A_COLLECTER

        # Isolation : impossible d'enregistrer une commande pour un client
        # d'un autre pressing.
        client = attrs.get("client")
        request = self.context.get("request")
        pressing = getattr(getattr(request, "user", None), "pressing", None)
        if client and pressing and client.pressing_id != pressing.id:
            raise serializers.ValidationError(
                {"client": "Ce client n'appartient pas à votre pressing."}
            )

        return attrs

    def create(self, validated_data):
        articles = validated_data.pop("articles")
        return create_commande(
            pressing=self.context["request"].user.pressing,
            articles=articles,
            **validated_data,
        )
