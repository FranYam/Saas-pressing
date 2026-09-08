"""Vues catalogue — CRUD staff (JWT pressing) + remplacement en masse."""
from django.db import transaction
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.response import Response

from apps.catalog.models import Tarif
from apps.catalog.serializers import TarifSerializer
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsSameTenant


class TarifViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """Gestion du catalogue par le pressing (Paramètres → Tarification).

    `PUT /catalog/bulk/` remplace tout le catalogue en une fois : la page
    Tarification envoie l'état complet, les lignes absentes sont supprimées.
    """

    serializer_class = TarifSerializer
    permission_classes = [IsSameTenant]
    queryset = Tarif.objects.select_related("pressing")

    @action(detail=False, methods=["put"], url_path="bulk")
    def bulk_replace(self, request):
        serializer = TarifSerializer(data=request.data.get("items", []), many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.get_queryset().delete()
            Tarif.objects.bulk_create(
                [Tarif(pressing_id=request.user.pressing_id, **item) for item in serializer.validated_data]
            )

        return Response(
            TarifSerializer(self.get_queryset(), many=True).data
        )
