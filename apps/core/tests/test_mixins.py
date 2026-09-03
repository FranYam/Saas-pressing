"""Tests du TenantScopedQuerysetMixin — critère d'acceptation Issue #2 :
le filtrage restreint bien les résultats au pressing de l'utilisateur connecté.
"""
from django.test import TestCase
from rest_framework import viewsets
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.core.mixins import TenantScopedQuerysetMixin
from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing

# Identifiants générés à l'exécution : aucun littéral dans le dépôt.
PASSWORD = fake_password()


class UserOnlyViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """ViewSet de test : les utilisateurs sont eux-mêmes scopés par pressing."""

    queryset = User.objects.all()
    serializer_class = None  # seul get_queryset est testé ici


class TenantScopedQuerysetMixinTests(TestCase):
    """Le pressing A ne doit jamais voir les utilisateurs du pressing B."""

    def setUp(self):
        factory = APIRequestFactory()
        self.request = factory.get("/")

        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")

        self.user_a1 = User.objects.create_user(
            username="70000001",
            password=PASSWORD,
            role=User.Role.GERANT,
            pressing=self.pressing_a,
        )
        User.objects.create_user(
            username="70000002",
            password=PASSWORD,
            role=User.Role.EMPLOYE,
            pressing=self.pressing_a,
        )
        User.objects.create_user(
            username="70000003",
            password=PASSWORD,
            role=User.Role.GERANT,
            pressing=self.pressing_b,
        )

    def queryset_for(self, user):
        self.request.user = user
        view = UserOnlyViewSet()
        view.request = self.request
        return view.get_queryset()

    def test_queryset_restricted_to_own_pressing(self):
        queryset = self.queryset_for(self.user_a1)
        usernames = set(queryset.values_list("username", flat=True))
        self.assertEqual(usernames, {"70000001", "70000002"})

    def test_other_pressing_never_leaks(self):
        queryset = self.queryset_for(self.user_a1)
        self.assertFalse(
            queryset.filter(pressing=self.pressing_b).exists(),
            "Les données du pressing B ne doivent jamais apparaître.",
        )

    def test_user_without_pressing_sees_nothing(self):
        """Fail-closed : sans pressing, on ne renvoie pas « tout » par défaut."""
        orphan = User.objects.create_user(username="70000009", password=PASSWORD)
        self.assertFalse(self.queryset_for(orphan).exists())

    def test_anonymous_user_sees_nothing(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(self.queryset_for(AnonymousUser()).exists())

    def test_superuser_sees_everything(self):
        """Le super-admin plateforme (sans pressing) passe outre le filtre."""
        User.objects.create_superuser(username="admin", password=PASSWORD)
        admin = User.objects.get(username="admin")
        self.assertEqual(self.queryset_for(admin).count(), 4)
