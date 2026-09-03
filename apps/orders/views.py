"""Vues orders : saisie au comptoir, suivi et cycle de vie (Issues #6-#7).

- Création limitée à POST (les articles ne s'éditent pas après coup) ;
- Le cycle de statut passe par l'action dédiée update_status, qui valide
  les transitions (impossible de livrer une commande non prête).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsSameTenant
from apps.orders.models import Commande
from apps.orders.serializers import CommandeSerializer
from apps.orders.services import update_commande_status


class CommandeViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """Commandes du pressing connecté — tout le personnel authentifié."""

    # PATCH est requis pour l'action update_status ; les updates génériques
    # sont volontairement fermés (voir update/partial_update ci-dessous).
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = (
        Commande.objects.select_related("client", "pressing").prefetch_related("articles")
    )
    serializer_class = CommandeSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]

    def get_queryset(self):
        queryset = super().get_queryset()  # filtrage tenant du mixin

        # Filtres pour l'écran de suivi : ?status=PRET&client=<uuid>
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param.strip().upper())

        client_param = self.request.query_params.get("client")
        if client_param:
            queryset = queryset.filter(client_id=client_param)

        return queryset

    def update(self, request, *args, **kwargs):
        """Édition générique fermée : passer par update_status."""
        return Response(
            {"detail": "Édition non supportée : utilisez /update_status/."},
            status=http_status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        description=(
            "Fait progresser le statut d'une commande. Transitions validées : "
            "RECU → EN_TRAITEMENT → PRET → LIVRE (RECU → PRET toléré ; "
            "LIVRE exige PRET)."
        )
    )
    @action(detail=True, methods=["patch"], url_path="update_status")
    def update_status(self, request, pk=None):
        commande = self.get_object()  # tenant-scoped : 404 si autre pressing

        new_status = str(request.data.get("status", "")).strip().upper()
        if new_status not in Commande.Status.values:
            return Response(
                {"status": f"Statut invalide. Valeurs acceptées : {', '.join(Commande.Status.values)}."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        commande = update_commande_status(commande=commande, new_status=new_status)
        return Response(CommandeSerializer(commande).data)
