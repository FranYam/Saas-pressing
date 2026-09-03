"""Vues orders : saisie au comptoir, suivi, cycle de vie et livraison
(Issues #6, #7, #11).

- Création limitée à POST (les articles ne s'éditent pas après coup) ;
- Le cycle de statut passe par update_status (transitions validées) ;
- La logistique passe par assign-courier (gérant), my-deliveries (coursier)
  et update-delivery (coursier assigné ou gérant).
"""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsGerant, IsSameTenant
from apps.deliveries.models import Courier
from apps.orders.models import Commande
from apps.orders.serializers import CommandeSerializer
from apps.orders.services import (
    assign_courier,
    update_commande_status,
    update_delivery_status,
)

User = get_user_model()


class CommandeViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """Commandes du pressing connecté — tout le personnel authentifié."""

    # PATCH est requis pour les actions update_status / update-delivery ;
    # les updates génériques sont volontairement fermés.
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = Commande.objects.select_related(
        "client", "pressing", "assigned_courier"
    ).prefetch_related("articles")
    serializer_class = CommandeSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]

    def get_queryset(self):
        queryset = super().get_queryset()  # filtrage tenant du mixin

        # Filtres de suivi : ?status=PRET&client=<uuid>&canal=EN_LIGNE
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param.strip().upper())

        canal_param = self.request.query_params.get("canal")
        if canal_param:
            queryset = queryset.filter(canal=canal_param.strip().upper())

        client_param = self.request.query_params.get("client")
        if client_param:
            queryset = queryset.filter(client_id=client_param)

        return queryset

    def get_permissions(self):
        # L'attribution d'un coursier est une décision du gérant (Issue #11).
        if self.action == "assign_courier":
            return [IsGerant()]
        return super().get_permissions()

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
                {
                    "status": (
                        "Statut invalide. Valeurs acceptées : "
                        f"{', '.join(Commande.Status.values)}."
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        commande = update_commande_status(commande=commande, new_status=new_status)
        return Response(CommandeSerializer(commande).data)

    @extend_schema(description="Assigne un coursier à la commande (gérant).")
    @action(detail=True, methods=["patch"], url_path="assign-courier")
    def assign_courier(self, request, pk=None):
        commande = self.get_object()

        courier = Courier.objects.filter(
            pk=request.data.get("courier"), pressing=request.user.pressing
        ).first()
        if courier is None:
            return Response(
                {"courier": "Coursier introuvable dans votre pressing."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            commande = assign_courier(commande=commande, courier=courier)
        except BusinessRuleError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(CommandeSerializer(commande).data)

    @extend_schema(
        description=(
            "Livraisons du coursier connecté : uniquement les commandes qui "
            "lui sont assignées (Issue #11). Filtre optionnel ?delivery_status=."
        )
    )
    @action(detail=False, methods=["get"], url_path="my-deliveries")
    def my_deliveries(self, request):
        queryset = self.get_queryset().filter(assigned_courier__user=request.user)

        delivery_param = request.query_params.get("delivery_status")
        if delivery_param:
            queryset = queryset.filter(delivery_status=delivery_param.strip().upper())

        page = self.paginate_queryset(queryset)
        serializer = CommandeSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        description=(
            "Fait progresser le statut de livraison (réservé au coursier "
            "assigné et au gérant). Cycle : À collecter → Collecté → "
            "À livrer → Livré."
        )
    )
    @action(detail=True, methods=["patch"], url_path="update-delivery")
    def update_delivery(self, request, pk=None):
        commande = self.get_object()

        # Seuls le coursier ASSIGNÉ et le gérant peuvent déplacer la livraison.
        is_assigned_courier = (
            commande.assigned_courier is not None
            and commande.assigned_courier.user_id == request.user.id
        )
        if not (is_assigned_courier or request.user.role == User.Role.GERANT):
            return Response(
                {
                    "detail": (
                        "Seul le coursier assigné (ou le gérant) peut mettre à "
                        "jour cette livraison."
                    )
                },
                status=http_status.HTTP_403_FORBIDDEN,
            )

        new_status = str(request.data.get("delivery_status", "")).strip().upper()
        if new_status not in Commande.DeliveryStatus.values:
            return Response(
                {
                    "delivery_status": (
                        "Statut invalide. Valeurs acceptées : "
                        f"{', '.join(Commande.DeliveryStatus.values)}."
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            commande = update_delivery_status(commande=commande, new_status=new_status)
        except BusinessRuleError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(CommandeSerializer(commande).data)
