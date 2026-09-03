"""Tests du modèle User."""
from django.test import TestCase

from apps.accounts.models import User
from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing


class UserModelTests(TestCase):
    def test_role_defaults_to_employe(self):
        user = User.objects.create_user(username="70112233", password=fake_password())

        self.assertEqual(user.role, User.Role.EMPLOYE)  # moindre privilège
        self.assertIsNone(user.pressing)
        self.assertFalse(user.is_gerant)

    def test_user_str_includes_role(self):
        pressing = Pressing.objects.create(name="Pressing A")
        user = User.objects.create_user(
            username="70112233",
            password=fake_password(),
            role=User.Role.GERANT,
            pressing=pressing,
        )
        self.assertEqual(str(user), "70112233 (Gérant)")
        self.assertTrue(user.is_gerant)
