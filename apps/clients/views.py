"""Vues clients : répertoire du pressing + recherche rapide par téléphone.

GET /api/v1/clients/?search=7012  → recherche par préfixe de numéro
(normalisé : « 70 12 » fonctionne aussi) ou par nom. Le ViewSet hérite de
TenantScopedQuerysetMixin : le pressing A ne voit ni ne trouve jamais les
clients du pressing B.
"""
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer
from apps.clients.services import normalize_phone
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsSameTenant


class ClientViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """CRUD clients — accessible à tout le personnel authentifié du pressing."""

    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]

    def get_queryset(self):
        queryset = super().get_queryset()  # filtrage tenant du mixin

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            digits = normalize_phone(search)
            conditions = Q()
            if digits:
                conditions |= Q(phone_number__istartswith=digits)
            if search:
                conditions |= Q(name__icontains=search)
            queryset = queryset.filter(conditions)

        return queryset
