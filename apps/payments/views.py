"""Vues payments : encaissements, solde client, créances (Issue #8).

Les paiements sont immuables (create/list/retrieve uniquement) : piste
d'audit financière — pas d'édition ni de suppression.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clients.models import Client
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsGerant, IsSameTenant
from apps.payments.models import Paiement
from apps.payments.serializers import ClientBalanceSerializer, PaiementSerializer
from apps.payments.services import get_client_balance, list_debtors


class PaiementViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """Règlements du pressing connecté — tout le personnel authentifié."""

    http_method_names = ["get", "post", "head", "options"]
    queryset = Paiement.objects.select_related("commande", "commande__client")
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]

    def get_queryset(self):
        queryset = super().get_queryset()  # filtrage tenant du mixin

        commande_param = self.request.query_params.get("commande")
        if commande_param:
            queryset = queryset.filter(commande_id=commande_param)

        return queryset

    def get_permissions(self):
        # Le relevé des créances est une vue financière : gérant uniquement.
        if self.action == "debtors":
            return [IsGerant()]
        return super().get_permissions()

    @action(detail=False, methods=["get"], url_path="client-balance")
    def client_balance(self, request):
        """Solde consolidé d'un client : ?client=<uuid> (fiche client)."""
        client_id = request.query_params.get("client")
        if not client_id:
            return Response(
                {"client": "Paramètre `client` requis."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        client = get_object_or_404(Client, pk=client_id, pressing=request.user.pressing)
        return Response(get_client_balance(client))

    @action(detail=False, methods=["get"], url_path="debtors")
    def debtors(self, request):
        """Clients du pressing ayant un solde débiteur > 0 (gérant)."""
        debtors = list_debtors(request.user.pressing)
        data = ClientBalanceSerializer(debtors, many=True).data
        return Response(data)
