"""Vues accounts : login JWT (avec claims), profil courant, gestion de l'équipe."""
from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.serializers import (
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
    LoginSerializer,
    UserSerializer,
)
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.permissions import IsGerant, IsSameTenant

User = get_user_model()


class LoginView(TokenObtainPairView):
    """POST /api/v1/accounts/login/ — paire de tokens JWT avec claims role + pressing_id."""

    serializer_class = LoginSerializer


class MeView(RetrieveAPIView):
    """GET /api/v1/accounts/me/ — profil de l'utilisateur connecté (tous rôles)."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class EmployeeViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    Gestion de l'équipe du pressing connecté — réservée au gérant.

    - List/retrieve : membres du pressing uniquement (TenantScopedQuerysetMixin) ;
    - Create : rôle EMPLOYE et pressing forcés depuis le gérant authentifié ;
    - Delete : désactivation (is_active=False), jamais de suppression physique —
      l'historique des commandes rattachées doit rester traçable.
    """

    queryset = User.objects.all()
    permission_classes = [IsGerant, IsSameTenant]

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        if self.action in ("update", "partial_update"):
            return EmployeeUpdateSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
