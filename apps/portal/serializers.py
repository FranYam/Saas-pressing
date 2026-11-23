"""Input serializers for public client portal operations."""
from rest_framework import serializers

from apps.clients.services import clean_phone
from apps.tenants.models import Pressing


class ClientRegisterInputSerializer(serializers.Serializer):
    pressing = serializers.PrimaryKeyRelatedField(queryset=Pressing.objects.all())
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(min_length=6, write_only=True, trim_whitespace=False)

    def validate_phone(self, value):
        return clean_phone(value)

class CollectionItemInputSerializer(serializers.Serializer):
    clothing_type = serializers.CharField(max_length=100, trim_whitespace=True)
    quantity = serializers.IntegerField(min_value=1, max_value=50)


class CollectionInputSerializer(serializers.Serializer):
    collect_address = serializers.CharField(trim_whitespace=True)
    creneau = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    articles = CollectionItemInputSerializer(many=True, allow_empty=False)

    def validate_collect_address(self, value):
        if not value:
            raise serializers.ValidationError("L'adresse de collecte est requise.")
        return value
