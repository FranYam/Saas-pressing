"""Tests deliveries & logistique (Issue #11) : coursiers, assignation,
vue my-deliveries (isolation stricte par coursier), cycle de livraison.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.deliveries.models import Courier
from apps.orders.models import Commande
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()


def make_commande(pressing, client, **kwargs):
    now = timezone.now()
    defaults = {
        "date_depot": now,
        "date_retrait_prevue": now + timedelta(days=2),
        "total_price": Decimal("1000.00"),
    }
    defaults.update(kwargs)
    return Commande.objects.create(pressing=pressing, client=client, **defaults)


class CourierManagementTests(TestCase):
    """CRUD /api/v1/deliveries/couriers/ — gérant."""

    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.gerant = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing_a,
        )
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.list_url = reverse("deliveries:couriers-list")

    def test_gerant_creates_courier_with_login(self):
        self.client.force_authenticate(user=self.gerant)
        response = self.client.post(
            self.list_url,
            {"name": "Issouf", "phone_number": "70 55 44 33", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        courier = Courier.objects.get(name="Issouf")
        self.assertEqual(courier.phone_number, "70554433")  # normalisé
        self.assertEqual(courier.pressing, self.pressing_a)
        # Compte de connexion créé avec le rôle COURSIER.
        self.assertIsNotNone(courier.user)
        self.assertEqual(courier.user.role, User.Role.COURSIER)

    def test_courier_can_login_with_phone(self):
        self.client.force_authenticate(user=self.gerant)
        self.client.post(
            self.list_url,
            {"name": "Issouf", "phone_number": "70554433", "password": PASSWORD},
            format="json",
        )

        login = APIClient().post(
            reverse("accounts:token_obtain_pair"),
            {"username": "70554433", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_duplicate_phone_within_pressing_rejected(self):
        Courier.objects.create(name="Issouf", phone_number="70554433", pressing=self.pressing_a)
        self.client.force_authenticate(user=self.gerant)

        response = self.client.post(
            self.list_url,
            {"name": "Doublon", "phone_number": "70554433", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_create_courier(self):
        self.client.force_authenticate(user=self.employe)
        response = self.client.post(
            self.list_url,
            {"name": "Issouf", "phone_number": "70554433", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_is_tenant_scoped(self):
        Courier.objects.create(name="A-Coursier", phone_number="70000001", pressing=self.pressing_a)
        Courier.objects.create(name="B-Coursier", phone_number="70000002", pressing=self.pressing_b)
        self.client.force_authenticate(user=self.gerant)

        response = self.client.get(self.list_url)

        names = {c["name"] for c in response.data["results"]}
        self.assertEqual(names, {"A-Coursier"})

    def test_delete_deactivates_courier_and_account(self):
        self.client.force_authenticate(user=self.gerant)
        courier = Courier.objects.create(name="Issouf", phone_number="70554433", pressing=self.pressing_a)
        courier_user = User.objects.create_user(
            username="70554433", password=PASSWORD,
            role=User.Role.COURSIER, pressing=self.pressing_a,
        )
        courier.user = courier_user
        courier.save()

        response = self.client.delete(reverse("deliveries:couriers-detail", args=[courier.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        courier.refresh_from_db()
        courier_user.refresh_from_db()
        self.assertFalse(courier.is_active)
        self.assertFalse(courier_user.is_active)


class DeliveryAssignmentTests(TestCase):
    """PATCH /api/v1/orders/{id}/assign-courier/ — gérant."""

    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.gerant = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing_a,
        )
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.commande = make_commande(
            self.pressing_a, self.client_obj,
            collect_address="Secteur 15, Ouaga",
            delivery_status=Commande.DeliveryStatus.A_COLLECTER,
        )
        self.courier = Courier.objects.create(
            name="Issouf", phone_number="70554433", pressing=self.pressing_a
        )
        self.client.force_authenticate(user=self.gerant)

    def assign(self, user, courier_id):
        self.client.force_authenticate(user=user)
        return self.client.patch(
            reverse("orders:commandes-assign-courier", args=[self.commande.id]),
            {"courier": str(courier_id)},
            format="json",
        )

    def test_gerant_assigns_courier(self):
        response = self.assign(self.gerant, self.courier.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.assigned_courier, self.courier)
        self.assertEqual(response.data["assigned_courier_name"], "Issouf")

    def test_employee_cannot_assign(self):
        response = self.assign(self.employe, self.courier.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_courier_from_other_pressing_rejected(self):
        courier_b = Courier.objects.create(name="B", phone_number="70000099", pressing=self.pressing_b)
        response = self.assign(self.gerant, courier_b.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MyDeliveriesTests(TestCase):
    """GET /api/v1/orders/my-deliveries/ — le coursier ne voit QUE ses livraisons."""

    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.gerant = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        # Deux coursiers du MÊME pressing : isolation par assignation.
        courier_1 = Courier.objects.create(name="Issouf", phone_number="70554433", pressing=self.pressing)
        courier_2 = Courier.objects.create(name="Ali", phone_number="70667788", pressing=self.pressing)
        self.user_courier_1 = User.objects.create_user(
            username="70554433", password=PASSWORD,
            role=User.Role.COURSIER, pressing=self.pressing,
        )
        user_courier_2 = User.objects.create_user(
            username="70667788", password=PASSWORD,
            role=User.Role.COURSIER, pressing=self.pressing,
        )
        courier_1.user = self.user_courier_1
        courier_1.save()
        courier_2.user = user_courier_2
        courier_2.save()
        self.courier_1 = courier_1

        self.commande_1 = make_commande(
            self.pressing, self.client_obj, assigned_courier=courier_1,
            delivery_status=Commande.DeliveryStatus.A_COLLECTER,
        )
        make_commande(  # assignée au coursier 2 — invisible pour le coursier 1
            self.pressing, self.client_obj, assigned_courier=courier_2,
            delivery_status=Commande.DeliveryStatus.A_LIVRER,
        )
        make_commande(  # sans livraison — invisible
            self.pressing, self.client_obj,
        )
        self.url = reverse("orders:commandes-my-deliveries")

    def test_courier_sees_only_assigned_commandes(self):
        self.client.force_authenticate(user=self.user_courier_1)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.commande_1.id))

    def test_unauthenticated_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_courier_user_sees_nothing(self):
        self.client.force_authenticate(user=self.gerant)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_assigned_courier_updates_delivery_cycle(self):
        detail_url = reverse(
            "orders:commandes-update-delivery", args=[self.commande_1.id]
        )
        self.client.force_authenticate(user=self.user_courier_1)

        for next_status in ("COLLECTE", "A_LIVRER", "LIVRE"):
            response = self.client.patch(
                detail_url, {"delivery_status": next_status}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, next_status)

        self.commande_1.refresh_from_db()
        self.assertEqual(self.commande_1.delivery_status, Commande.DeliveryStatus.LIVRE)

    def test_delivery_skip_transition_rejected(self):
        detail_url = reverse(
            "orders:commandes-update-delivery", args=[self.commande_1.id]
        )
        self.client.force_authenticate(user=self.user_courier_1)

        response = self.client.patch(detail_url, {"delivery_status": "LIVRE"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_courier_cannot_update(self):
        """Un coursier ne touche pas la livraison d'un collègue."""
        other = User.objects.create_user(
            username="70778899", password=PASSWORD,
            role=User.Role.COURSIER, pressing=self.pressing,
        )
        detail_url = reverse(
            "orders:commandes-update-delivery", args=[self.commande_1.id]
        )
        self.client.force_authenticate(user=other)

        response = self.client.patch(detail_url, {"delivery_status": "COLLECTE"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_gerant_can_update_delivery(self):
        detail_url = reverse(
            "orders:commandes-update-delivery", args=[self.commande_1.id]
        )
        self.client.force_authenticate(user=self.gerant)

        response = self.client.patch(detail_url, {"delivery_status": "COLLECTE"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
