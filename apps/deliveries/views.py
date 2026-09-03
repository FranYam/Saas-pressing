"""Vues deliveries : gestion des coursiers par le gérant (Issue #11)."""
from rest_framework import status as http_status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsGerant, IsSameTenant
from apps.deliveries.serializers import (
    CourierCreateSerializer,
    CourierSerializer,
)
from apps.deliveries.services import create_courier, deactivate_courier
from apps.deliveries.models import Courier


class CourierViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    Coursiers du pressing : lecture pour tout le personnel, création et
    désactivation réservées au gérant.

    DELETE = désactivation (profil + compte de connexion), jamais de
    suppression physique : l'historique des livraisons reste traçable.
    """

    http_method_names = ["get", "post", "delete", "head", "options"]
    queryset = Courier.objects.select_related("user")
    serializer_class = CourierSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsGerant()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = CourierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            courier = create_courier(
                pressing=request.user.pressing,
                name=serializer.validated_data["name"],
                phone_number=serializer.validated_data["phone_number"],
                password=serializer.validated_data["password"],
            )
        except BusinessRuleError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(
            CourierSerializer(courier).data, status=http_status.HTTP_201_CREATED
        )

    def perform_destroy(self, instance):
        deactivate_courier(instance)
