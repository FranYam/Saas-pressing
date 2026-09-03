"""Vues payments_gateway : initiation au comptoir + suivi des demandes."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsSameTenant
from apps.orders.models import Commande
from apps.payments_gateway.models import MobileMoneyRequest
from apps.payments_gateway.serializers import (
    InitiateMobileMoneySerializer,
    MobileMoneyRequestSerializer,
)
from apps.payments_gateway.services import initiate_mobile_money_payment


class InitiateMobileMoneyView(APIView):
    """POST /api/v1/payments-gateway/initiate/ — déclenche un push USSD/STK."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InitiateMobileMoneySerializer,
        responses={201: MobileMoneyRequestSerializer, 400: None, 404: None},
        description=(
            "Déclenche un push Mobile Money (Orange/Moov) pour le reste à "
            "payer de la commande. Le montant est calculé serveur."
        ),
    )
    def post(self, request):
        serializer = InitiateMobileMoneySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        commande = get_object_or_404(
            Commande, pk=serializer.validated_data["commande"], pressing=request.user.pressing
        )

        try:
            mm_request = initiate_mobile_money_payment(
                commande=commande,
                phone_number=serializer.validated_data["phone_number"],
                operator=serializer.validated_data["operator"],
            )
        except BusinessRuleError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(
            MobileMoneyRequestSerializer(mm_request).data,
            status=http_status.HTTP_201_CREATED,
        )


class MobileMoneyRequestViewSet(TenantScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Suivi des demandes Mobile Money du pressing connecté (lecture seule)."""

    queryset = MobileMoneyRequest.objects.select_related("commande")
    serializer_class = MobileMoneyRequestSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
