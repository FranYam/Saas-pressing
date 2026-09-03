"""Permissions multi-tenant et par rôle (Issue #2, complétées aux issues #4, #11...)."""
from django.contrib.auth import get_user_model
from rest_framework import permissions


class IsSameTenant(permissions.BasePermission):
    """
    Permission objet : la ressource visée (retrieve/update/destroy) doit
    appartenir au pressing de l'utilisateur connecté.

    Se cumule avec `TenantScopedQuerysetMixin` : le mixin filtre les listes,
    cette permission protège les accès unitaires.
    """

    message = "Cette ressource n'appartient pas à votre pressing."

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        obj_pressing_id = getattr(obj, "pressing_id", None)
        return obj_pressing_id is not None and obj_pressing_id == user.pressing_id


class IsGerant(permissions.BasePermission):
    """Accès réservé au rôle Gérant (statistiques financières, branding du pressing)."""

    message = "Action réservée au gérant du pressing."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.role == get_user_model().Role.GERANT


class IsEmploye(permissions.BasePermission):
    """Accès réservé au rôle Employé (opérations de comptoir)."""

    message = "Action réservée aux employés du pressing."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.role == get_user_model().Role.EMPLOYE


class IsCoursier(permissions.BasePermission):
    """Accès réservé au rôle Coursier (livraisons assignées)."""

    message = "Action réservée aux coursiers du pressing."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.role == get_user_model().Role.COURSIER
