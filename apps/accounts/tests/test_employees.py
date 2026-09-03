"""Tests de gestion de l'équipe & JWT (Issue #4) : RBAC, isolation tenant,
désactivation au lieu de suppression, claims du token.

Fixtures de test uniquement — mots de passe factices (voir .gitguardian.yml).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.state import token_backend

from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing

User = get_user_model()
# Identifiants générés à l'exécution : aucun littéral dans le dépôt.
PASSWORD = fake_password()
NEW_PASSWORD = fake_password()


class EmployeeManagementTests(TestCase):
    """CRUD /api/v1/accounts/employees/ — réservé au gérant du pressing."""

    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")

        self.gerant_a = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing_a,
        )
        self.employe_a = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.gerant_b = User.objects.create_user(
            username="70000003", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing_b,
        )
        self.employe_b = User.objects.create_user(
            username="70000004", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_b,
        )
        self.list_url = reverse("accounts:employees-list")

    def detail_url(self, user):
        return reverse("accounts:employees-detail", args=[user.id])

    def test_gerant_creates_employee_in_own_pressing(self):
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.post(
            self.list_url,
            {"username": "70111222", "password": PASSWORD, "first_name": "Salif"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        employee = User.objects.get(username="70111222")
        self.assertEqual(employee.pressing, self.pressing_a)
        self.assertEqual(employee.role, User.Role.EMPLOYE)
        # Le mot de passe n'est jamais renvoyé dans la réponse.
        self.assertNotIn("password", response.data)

    def test_pressing_and_role_forced_from_authenticated_gerant(self):
        """Le `pressing` du payload est ignoré : impossible de créer ailleurs
        que dans son propre pressing, impossible de créer un gérant."""
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.post(
            self.list_url,
            {
                "username": "70111223",
                "password": PASSWORD,
                "pressing": str(self.pressing_b.id),
                "role": "GERANT",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        employee = User.objects.get(username="70111223")
        self.assertEqual(employee.pressing, self.pressing_a)
        self.assertEqual(employee.role, User.Role.EMPLOYE)

    def test_employee_cannot_manage_team(self):
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.post(
            self.list_url, {"username": "70999111", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_gets_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_tenant_scoped(self):
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {user["username"] for user in response.data["results"]}
        self.assertEqual(usernames, {"70000001", "70000002"})  # équipe A uniquement

    def test_detail_cross_tenant_returns_404(self):
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.get(self.detail_url(self.employe_b))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_gerant_can_update_employee(self):
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.patch(
            self.detail_url(self.employe_a), {"first_name": "Ali"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employe_a.refresh_from_db()
        self.assertEqual(self.employe_a.first_name, "Ali")

    def test_gerant_can_reset_employee_password(self):
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.patch(
            self.detail_url(self.employe_a),
            {"password": NEW_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        login = self.client.post(
            reverse("accounts:token_obtain_pair"),
            {"username": "70000002", "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_delete_deactivates_instead_of_removing(self):
        """Désactivation (is_active=False) : l'historique reste traçable."""
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.delete(self.detail_url(self.employe_a))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.employe_a.refresh_from_db()
        self.assertFalse(self.employe_a.is_active)
        self.assertTrue(User.objects.filter(username="70000002").exists())

    def test_deactivated_employee_cannot_login(self):
        self.employe_a.is_active = False
        self.employe_a.save()

        response = self.client.post(
            reverse("accounts:token_obtain_pair"),
            {"username": "70000002", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeEndpointTests(TestCase):
    """GET /api/v1/accounts/me/ + claims personnalisés du JWT."""

    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing,
        )

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_own_profile(self):
        self.client.force_authenticate(user=self.employe)

        response = self.client.get(reverse("accounts:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "70000002")
        self.assertEqual(response.data["role"], "EMPLOYE")
        self.assertEqual(str(response.data["pressing"]), str(self.pressing.id))

    def test_login_token_carries_role_and_pressing_claims(self):
        gerant = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing,
        )

        response = self.client.post(
            reverse("accounts:token_obtain_pair"),
            {"username": "70000001", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = token_backend.decode(response.data["access"])
        self.assertEqual(payload["role"], "GERANT")
        self.assertEqual(payload["pressing_id"], str(self.pressing.id))
