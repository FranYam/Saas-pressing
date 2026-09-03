"""Tests de l'API clients (Issue #5) : CRUD scopé par pressing, unicité par
pressing, recherche par préfixe téléphone, isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()


class ClientAPITests(TestCase):
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
        self.employe_b = User.objects.create_user(
            username="70000003", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_b,
        )
        self.list_url = reverse("clients:clients-list")

    def detail_url(self, client):
        return reverse("clients:clients-detail", args=[client.id])

    # ------------------------------------------------------------- création

    def test_employee_can_create_client_with_normalized_phone(self):
        """L'employé au comptoir crée la fiche ; « 70 12 34 56 » → « 70123456 »."""
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.post(
            self.list_url,
            {"name": "Awa Ouédraogo", "phone_number": "70 12 34 56"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["phone_number"], "70123456")
        client = Client.objects.get(name="Awa Ouédraogo")
        self.assertEqual(client.pressing, self.pressing_a)  # forcé côté serveur

    def test_invalid_phone_rejected(self):
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.post(
            self.list_url, {"name": "Awa", "phone_number": "123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)

    def test_duplicate_phone_within_same_pressing_rejected(self):
        Client.objects.create(name="Awa", phone_number="70123456", pressing=self.pressing_a)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.post(
            self.list_url, {"name": "Doublon", "phone_number": "70 12 34 56"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_phone_in_other_pressing_allowed(self):
        """Unicité par pressing : le même numéro peut exister chez B et A."""
        Client.objects.create(name="Client B", phone_number="70123456", pressing=self.pressing_b)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.post(
            self.list_url, {"name": "Client A", "phone_number": "70123456"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ------------------------------------------------------------- recherche

    def test_search_by_phone_prefix(self):
        Client.objects.create(name="Awa", phone_number="70123456", pressing=self.pressing_a)
        Client.objects.create(name="Boukary", phone_number="70998877", pressing=self.pressing_a)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url, {"search": "7012"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["phone_number"], "70123456")

    def test_search_normalizes_input(self):
        """« 70 12 » saisit au comptoir trouve les numéros en 7012…"""
        Client.objects.create(name="Awa", phone_number="70123456", pressing=self.pressing_a)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url, {"search": "70 12"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_search_by_name(self):
        Client.objects.create(name="Awa Ouédraogo", phone_number="70123456", pressing=self.pressing_a)
        Client.objects.create(name="Boukary Sawadogo", phone_number="70998877", pressing=self.pressing_a)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url, {"search": "ouédra"})

        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Awa Ouédraogo")

    def test_search_is_tenant_scoped(self):
        """Critère d'acceptation : A ne trouve jamais les clients de B."""
        Client.objects.create(name="Client A", phone_number="70123456", pressing=self.pressing_a)
        Client.objects.create(name="Client B", phone_number="70129999", pressing=self.pressing_b)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url, {"search": "7012"})

        phones = [c["phone_number"] for c in response.data["results"]]
        self.assertIn("70123456", phones)
        self.assertNotIn("70129999", phones)

    # -------------------------------------------------------- isolation CRUD

    def test_unauthenticated_gets_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_tenant_scoped(self):
        Client.objects.create(name="Client A", phone_number="70123456", pressing=self.pressing_a)
        Client.objects.create(name="Client B", phone_number="70998877", pressing=self.pressing_b)
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.list_url)

        names = {c["name"] for c in response.data["results"]}
        self.assertEqual(names, {"Client A"})

    def test_detail_cross_tenant_returns_404(self):
        client_b = Client.objects.create(
            name="Client B", phone_number="70998877", pressing=self.pressing_b
        )
        self.client.force_authenticate(user=self.employe_a)

        response = self.client.get(self.detail_url(client_b))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_and_delete_own_pressing_client(self):
        client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.client.force_authenticate(user=self.gerant_a)

        response = self.client.patch(
            self.detail_url(client_a), {"name": "Awa Ouédraogo"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(self.detail_url(client_a))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Client.objects.filter(name="Awa Ouédraogo").exists())
