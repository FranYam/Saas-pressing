"""Vues tenants : inscription publique et profil de l'établissement.

Le profil expose le branding (logo + couleurs) que la PWA récupère au
chargement via GET /api/v1/tenants/profile/ pour habiller dynamiquement
l'interface. La modification de la marque est réservée au gérant — un
employé ne peut pas changer l'identité visuelle du pressing.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsGerant
from apps.tenants.serializers import (
    PressingSerializer,
    RegisterPressingSerializer,
)
from apps.tenants.services import register_pressing


class PressingRegisterView(APIView):
    """POST /api/v1/tenants/register/ — inscription publique (pressing + gérant)."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterPressingSerializer,
        responses={status.HTTP_201_CREATED: PressingSerializer},
        description=(
            "Inscrit un pressing et son utilisateur gérant en une requête "
            "atomique. Réponse : détails de l'établissement + paire de tokens "
            "JWT (`access` / `refresh`)."
        ),
    )
    def post(self, request):
        serializer = RegisterPressingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        gerant_data = data.pop("gerant")
        pressing, gerant = register_pressing(
            pressing_data=data, gerant_data=gerant_data
        )

        # Tokens retournés pour connecter le gérant immédiatement, sans
        # second aller-retour vers /accounts/login/.
        tokens = RefreshToken.for_user(gerant)
        return Response(
            {
                "pressing": PressingSerializer(pressing).data,
                "tokens": {"refresh": str(tokens), "access": str(tokens.access_token)},
            },
            status=status.HTTP_201_CREATED,
        )


class PressingProfileView(RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/tenants/profile/ — branding du pressing connecté."""

    serializer_class = PressingSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        pressing = self.request.user.pressing
        if pressing is None:
            raise NotFound("Aucun pressing associé à ce compte.")
        return pressing

    def get_permissions(self):
        # Lecture ouverte à tous les membres du pressing (l'employé a besoin
        # des couleurs pour l'UI) ; la customisation est réservée au gérant.
        if self.request.method in ("PUT", "PATCH"):
            return [IsGerant()]
        return [IsAuthenticated()]
