"""Sérialiseur clients : création/lecture, `pressing` forcé côté serveur."""
from rest_framework import serializers

from apps.clients.models import Client
from apps.clients.services import clean_phone


class ClientSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=32)

    class Meta:
        model = Client
        fields = ["id", "name", "phone_number", "pressing", "created_at"]
        read_only_fields = ["id", "pressing", "created_at"]

    def validate_phone_number(self, value):
        return clean_phone(value)

    def validate(self, attrs):
        """Unicité (phone_number, pressing) avec un message clair en 400."""
        request = self.context.get("request")
        pressing = getattr(getattr(request, "user", None), "pressing", None)
        phone = attrs.get("phone_number")

        if phone and pressing:
            queryset = Client.objects.filter(phone_number=phone, pressing=pressing)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"phone_number": "Ce numéro existe déjà pour ce pressing."}
                )
        return attrs

    def create(self, validated_data):
        # Le pressing ne vient JAMAIS du payload : déduit de l'utilisateur
        # connecté (isolation multi-tenant).
        request = self.context["request"]
        return Client.objects.create(**validated_data, pressing=request.user.pressing)
