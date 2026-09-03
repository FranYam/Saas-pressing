"""Tests de l'API orders (Issue #6) : création transactionnelle, total calculé
serveur, isolation multi-tenant (client et commandes).
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.utils import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.orders.models import Commande, OrderItem
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()


def payload_for(client_id, articles=None):
    if articles is None:
        articles = [
            {"clothing_type": "Pantalon", "quantity": 2, "unit_price": "1500.00"},
            {"clothing_type": "Chemise", "quantity": 1, "unit_price": "2000.00"},
        ]
    return {
        "client": str(client_id),
        "date_retrait_prevue": (timezone.now() + timedelta(days=2)).isoformat(),
        "articles": articles,
    }


class CommandeCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe_a = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.client_b = Client.objects.create(
            name="Boukary", phone_number="70998877", pressing=self.pressing_b
        )
        self.list_url = reverse("orders:commandes-list")
        self.client.force_authenticate(user=self.employe_a)

    def test_employee_creates_commande_with_nested_articles(self):
        response = self.client.post(self.list_url, payload_for(self.client_a.id), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        commande = Commande.objects.get(id=response.data["id"])
        self.assertEqual(commande.pressing, self.pressing_a)  # forcé serveur
        self.assertEqual(commande.status, Commande.Status.RECU)
        self.assertEqual(commande.canal, Commande.Canal.COMPTOIR)
        self.assertEqual(commande.articles.count(), 2)
        # Articles imbriqués dans la réponse
        types = {a["clothing_type"] for a in response.data["articles"]}
        self.assertEqual(types, {"Pantalon", "Chemise"})

    def test_total_price_computed_server_side(self):
        """2 × 1500 + 1 × 2000 = 5000 — même si le payload tente d'imposer un total."""
        payload = payload_for(self.client_a.id)
        payload["total_price"] = "1.00"  # doit être ignoré (read_only)

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        commande = Commande.objects.get(id=response.data["id"])
        self.assertEqual(commande.total_price, Decimal("5000.00"))

    def test_rollback_if_article_insertion_fails(self):
        """Critère d'acceptation : si un article échoue, aucune commande en base."""
        with patch(
            "apps.orders.services.OrderItem.objects.bulk_create",
            side_effect=DatabaseError("Échec simulé de l'insertion article"),
        ):
            with self.assertRaises(DatabaseError):
                self.client.post(
                    self.list_url, payload_for(self.client_a.id), format="json"
                )

        self.assertEqual(Commande.objects.count(), 0)  # rollback complet
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_client_from_other_pressing_rejected(self):
        response = self.client.post(self.list_url, payload_for(self.client_b.id), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client", response.data)
        self.assertEqual(Commande.objects.count(), 0)

    def test_empty_articles_rejected(self):
        response = self.client.post(
            self.list_url, payload_for(self.client_a.id, articles=[]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_date_retrait_rejected(self):
        payload = payload_for(self.client_a.id)
        del payload["date_retrait_prevue"]

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CommandeListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe_a = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.client_b = Client.objects.create(
            name="Boukary", phone_number="70998877", pressing=self.pressing_b
        )
        now = timezone.now()
        self.commande_recue = Commande.objects.create(
            pressing=self.pressing_a, client=self.client_a,
            date_depot=now, date_retrait_prevue=now + timedelta(days=2),
            total_price=Decimal("1000.00"),
        )
        self.commande_prete = Commande.objects.create(
            pressing=self.pressing_a, client=self.client_a,
            status=Commande.Status.PRET,
            date_depot=now, date_retrait_prevue=now + timedelta(days=1),
            total_price=Decimal("2000.00"),
        )
        Commande.objects.create(  # pressing B — jamais visible pour A
            pressing=self.pressing_b, client=self.client_b,
            date_depot=now, date_retrait_prevue=now + timedelta(days=3),
            total_price=Decimal("9999.00"),
        )
        self.list_url = reverse("orders:commandes-list")
        self.client.force_authenticate(user=self.employe_a)

    def test_unauthenticated_gets_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_tenant_scoped(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {str(c["id"]) for c in response.data["results"]}
        expected = {str(self.commande_recue.id), str(self.commande_prete.id)}
        self.assertEqual(ids, expected)

    def test_filter_by_status(self):
        response = self.client.get(self.list_url, {"status": "PRET"})

        ids = [str(c["id"]) for c in response.data["results"]]
        self.assertEqual(ids, [str(self.commande_prete.id)])

    def test_filter_by_client(self):
        response = self.client.get(self.list_url, {"client": str(self.client_a.id)})

        self.assertEqual(len(response.data["results"]), 2)

    def test_detail_includes_nested_articles(self):
        OrderItem.objects.create(
            commande=self.commande_recue, clothing_type="Bazin",
            quantity=3, unit_price=Decimal("2500.00"),
        )
        detail_url = reverse("orders:commandes-detail", args=[self.commande_recue.id])

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["articles"]), 1)
        self.assertEqual(response.data["articles"][0]["clothing_type"], "Bazin")

    def test_detail_cross_tenant_returns_404(self):
        commande_b = Commande.objects.filter(pressing=self.pressing_b).first()
        detail_url = reverse("orders:commandes-detail", args=[commande_b.id])

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
