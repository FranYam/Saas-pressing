"""Sérialiseurs catalogue — lecture portail et gestion staff."""
from rest_framework import serializers

from apps.catalog.models import Tarif


class TarifSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarif
        fields = ["id", "name", "category", "price", "is_active"]
        read_only_fields = ["id"]


class TarifBulkSerializer(serializers.Serializer):
    """Remplacement atomique du catalogue complet (page Paramètres → Tarification)."""

    items = TarifSerializer(many=True)
