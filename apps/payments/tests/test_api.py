"""Tests de l'API payments (Issue #8) : encaissements, soldes, créances."""
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
from apps.orders.models import Commande
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()


def make_commande(pressing, client, total, **kwargs):
    now = timezone.now()
    defaults = {
        "date_depot": now,
        "date_retrait_prevue": now + timedelta(days=2),
    }
    defaults.update(kwargs)
    return Commande.objects.create(
        pressing=pressing, client=client, total_price=Decimal(total), **defaults
    )


class PaiementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe_a = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.gerant_a = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing_a,
        )
        self.client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.commande = make_commande(
            self.pressing_a, self.client_a, "5000.00", ticket_number="TX-2609-001"
        )
        self.list_url = reverse("payments:paiements-list")
        self.client.force_authenticate(user=self.employe_a)

    def test_employee_registers_cash_payment(self):
        response = self.client.post(
            self.list_url,
            {"commande": str(self.commande.id), "amount": "5000.00", "mode": "ESPECES"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "PAYE")
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.PAYE)

    def test_status_is_computed_not_taken_from_payload(self):
        response = self.client.post(
            self.list_url,
            {
                "commande": str(self.commande.id),
                "amount": "1000.00",
                "mode": "ESPECES",
                "status": "PAYE",  # doit être ignoré : calculé serveur
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "PARTIEL")  # 1000/5000

    def test_overpayment_returns_400(self):
        response = self.client.post(
            self.list_url,
            {"commande": str(self.commande.id), "amount": "9000.00", "mode": "ESPECES"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_credit_registration_via_api(self):
        response = self.client.post(
            self.list_url,
            {"commande": str(self.commande.id), "amount": "0.00", "mode": "CREDIT"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "CREDIT")

    def test_payment_on_other_pressing_commande_rejected(self):
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        commande_b = make_commande(
            self.pressing_b, client_b, "2000.00", ticket_number="TX-2609-002"
        )

        response = self.client.post(
            self.list_url,
            {"commande": str(commande_b.id), "amount": "100.00", "mode": "ESPECES"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("commande", response.data)

    def test_unauthenticated_gets_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_tenant_scoped(self):
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        commande_b = make_commande(
            self.pressing_b, client_b, "2000.00", ticket_number="TX-2609-003"
        )
        from apps.payments.models import Paiement

        Paiement.objects.create(
            commande=self.commande, amount=Decimal("500.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing_a,
        )
        Paiement.objects.create(
            commande=commande_b, amount=Decimal("100.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing_b,
        )

        response = self.client.get(self.list_url)

        amounts = {str(p["amount"]) for p in response.data["results"]}
        self.assertEqual(amounts, {"500.00"})  # jamais le paiement du pressing B

    def test_payments_are_immutable(self):
        """Aucune édition/suppression : piste d'audit financière."""
        from apps.payments.models import Paiement

        paiement = Paiement.objects.create(
            commande=self.commande, amount=Decimal("500.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing_a,
        )
        detail_url = reverse("payments:paiements-detail", args=[paiement.id])

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ClientBalanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing,
        )
        self.gerant = User.objects.create_user(
            username="70000001", password=PASSWORD,
            role=User.Role.GERANT, pressing=self.pressing,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        commande = make_commande(
            self.pressing, self.client_obj, "3000.00", ticket_number="TX-2609-010"
        )
        from apps.payments.models import Paiement

        Paiement.objects.create(
            commande=commande, amount=Decimal("1000.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing,
        )
        self.balance_url = reverse("payments:paiements-client-balance")
        self.debtors_url = reverse("payments:paiements-debtors")

    def test_client_balance_returns_consolidated_numbers(self):
        self.client.force_authenticate(user=self.employe)

        response = self.client.get(self.balance_url, {"client": str(self.client_obj.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["total_due"]), Decimal("3000.00"))
        self.assertEqual(Decimal(response.data["total_paid"]), Decimal("1000.00"))
        self.assertEqual(Decimal(response.data["balance"]), Decimal("2000.00"))
        self.assertEqual(len(response.data["unpaid_commandes"]), 1)

    def test_client_balance_requires_client_param(self):
        self.client.force_authenticate(user=self.employe)

        response = self.client.get(self.balance_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_balance_cross_tenant_404(self):
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        self.client.force_authenticate(user=self.employe)

        response = self.client.get(self.balance_url, {"client": str(client_b.id)})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_debtors_listed_for_gerant(self):
        self.client.force_authenticate(user=self.gerant)

        response = self.client.get(self.debtors_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["client"]["name"], "Awa")
        self.assertEqual(
            Decimal(str(response.data[0]["balance"])), Decimal("2000.00")
        )

    def test_debtors_forbidden_for_employee(self):
        """Critère d'acceptation : les vues financières sont réservées au gérant."""
        self.client.force_authenticate(user=self.employe)

        response = self.client.get(self.debtors_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
