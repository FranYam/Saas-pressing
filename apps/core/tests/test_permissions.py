"""Tests de la permission IsSameTenant — accès unitaires (detail/update/destroy)."""
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.core.permissions import IsEmploye, IsGerant, IsSameTenant
from apps.tenants.models import Pressing


class IsSameTenantTests(TestCase):
    """Un objet du pressing B doit être inaccessible à un utilisateur du pressing A."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.user_a = User.objects.create_user(
            username="70000001",
            password="secret123",
            role=User.Role.GERANT,
            pressing=self.pressing_a,
        )

    def authenticated_request(self, user):
        request = self.factory.get("/")
        force_authenticate(request, user=user)
        return request

    def test_same_tenant_object_allowed(self):
        obj = User.objects.create_user(
            username="70000002", password="secret123", pressing=self.pressing_a
        )
        request = self.authenticated_request(self.user_a)
        self.assertTrue(IsSameTenant().has_object_permission(request, None, obj))

    def test_cross_tenant_object_denied(self):
        obj = User.objects.create_user(
            username="70000003", password="secret123", pressing=self.pressing_b
        )
        request = self.authenticated_request(self.user_a)
        self.assertFalse(IsSameTenant().has_object_permission(request, None, obj))

    def test_object_without_pressing_denied(self):
        """Fail-closed : une ressource sans pressing n'est accessible à personne."""
        obj = User.objects.create_user(username="70000009", password="secret123")
        request = self.authenticated_request(self.user_a)
        self.assertFalse(IsSameTenant().has_object_permission(request, None, obj))

    def test_anonymous_denied(self):
        obj = User.objects.create_user(
            username="70000002", password="secret123", pressing=self.pressing_a
        )
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertFalse(IsSameTenant().has_object_permission(request, None, obj))

    def test_superuser_allowed(self):
        admin = User.objects.create_superuser(username="admin", password="secret123")
        obj = User.objects.create_user(
            username="70000003", password="secret123", pressing=self.pressing_b
        )
        request = self.authenticated_request(admin)
        self.assertTrue(IsSameTenant().has_object_permission(request, None, obj))


class RolePermissionTests(TestCase):
    """IsGerant / IsEmploye protègent les endpoints par rôle (Issue #4)."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.gerant = User.objects.create_user(
            username="70000001",
            password="secret123",
            role=User.Role.GERANT,
            pressing=self.pressing,
        )
        self.employe = User.objects.create_user(
            username="70000002",
            password="secret123",
            role=User.Role.EMPLOYE,
            pressing=self.pressing,
        )

    def request_for(self, user):
        request = self.factory.get("/")
        force_authenticate(request, user=user)
        return request

    def test_is_gerant_allows_gerant(self):
        self.assertTrue(IsGerant().has_permission(self.request_for(self.gerant), None))

    def test_is_gerant_denies_employe(self):
        self.assertFalse(IsGerant().has_permission(self.request_for(self.employe), None))

    def test_is_employe_allows_employe(self):
        self.assertTrue(IsEmploye().has_permission(self.request_for(self.employe), None))

    def test_is_employe_denies_gerant(self):
        self.assertFalse(IsEmploye().has_permission(self.request_for(self.gerant), None))
