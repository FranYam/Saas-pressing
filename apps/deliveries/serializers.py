"""Sérialiseur deliveries : coursiers du pressing."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.deliveries.models import Courier

User = get_user_model()


class CourierSerializer(serializers.ModelSerializer):
    """Représentation d'un coursier (lecture)."""

    class Meta:
        model = Courier
        fields = ["id", "name", "phone_number", "is_active", "created_at"]
        read_only_fields = fields


class CourierCreateSerializer(serializers.Serializer):
    """Création d'un coursier : profil + compte de connexion (rôle COURSIER)."""

    name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=32)
    password = serializers.CharField(
        write_only=True, validators=[validate_password], style={"input_type": "password"}
    )
