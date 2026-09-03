"""Tests du cycle de vie & tickets (Issue #7) : génération TX-YYMM-NNN
(sequentielle, reset mensuel, unicité par pressing), transitions de statut
validées, reçu texte.
"""
import re
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.orders.models import Commande, OrderItem
from apps.orders.services import format_receipt, generate_ticket_number
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()
TICKET_RE = re.compile(r"^TX-\d{4}-\d{3}$")  # TX-YYMM-NNN


def make_commande(pressing, client, **kwargs):
    now = timezone.now()
    defaults = {
        "date_depot": now,
        "date_retrait_prevue": now + timedelta(days=2),
        "total_price": Decimal("1000.00"),
    }
    defaults.update(kwargs)
    return Commande.objects.create(pressing=pressing, client=client, **defaults)


class TicketGeneratorTests(TestCase):
    def setUp(self):
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )

    def test_first_ticket_of_month_starts_at_001(self):
        ticket = generate_ticket_number(self.pressing_a, today=date(2026, 9, 1))
        self.assertEqual(ticket, "TX-2609-001")

    def test_sequence_increments_within_month(self):
        make_commande(self.pressing_a, self.client_a, ticket_number="TX-2608-005")
        ticket = generate_ticket_number(self.pressing_a, today=date(2026, 8, 31))
        self.assertEqual(ticket, "TX-2608-006")

    def test_sequence_resets_each_month(self):
        make_commande(self.pressing_a, self.client_a, ticket_number="TX-2608-042")
        ticket = generate_ticket_number(self.pressing_a, today=date(2026, 9, 1))
        self.assertEqual(ticket, "TX-2609-001")

    def test_sequence_is_independent_per_pressing(self):
        """Chaque pressing a sa propre numérotation (unicité par pressing)."""
        make_commande(self.pressing_a, self.client_a, ticket_number="TX-2609-007")
        ticket_b = generate_ticket_number(self.pressing_b, today=date(2026, 9, 15))
        self.assertEqual(ticket_b, "TX-2609-001")


class TicketOnCreateTests(TestCase):
    """Critère d'acceptation : ticket généré automatiquement à la création."""

    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.client.force_authenticate(user=self.employe)

    def payload(self):
        return {
            "client": str(self.client_obj.id),
            "date_retrait_prevue": (timezone.now() + timedelta(days=2)).isoformat(),
            "articles": [{"clothing_type": "Bazin", "quantity": 1, "unit_price": "3000.00"}],
        }

    def test_ticket_generated_on_api_create(self):
        response = self.client.post(reverse("orders:commandes-list"), self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertRegex(response.data["ticket_number"], TICKET_RE)

    def test_tickets_are_sequential(self):
        first = self.client.post(reverse("orders:commandes-list"), self.payload(), format="json")
        second = self.client.post(reverse("orders:commandes-list"), self.payload(), format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        seq1 = int(first.data["ticket_number"][-3:])
        seq2 = int(second.data["ticket_number"][-3:])
        self.assertEqual(seq2, seq1 + 1)


class StatusTransitionTests(TestCase):
    """PATCH /api/v1/orders/<id>/update_status/ — transitions validées."""

    def setUp(self):
        self.client = APIClient()
        self.pressing_a = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing_a,
        )
        self.client_a = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing_a
        )
        self.commande = make_commande(self.pressing_a, self.client_a)
        OrderItem.objects.create(
            commande=self.commande, clothing_type="Chemise",
            quantity=2, unit_price=Decimal("500.00"),
        )
        self.client.force_authenticate(user=self.employe)

    def update_status(self, commande, new_status):
        url = reverse("orders:commandes-update-status", args=[commande.id])
        return self.client.patch(url, {"status": new_status}, format="json")

    def test_valid_full_cycle(self):
        r1 = self.update_status(self.commande, "EN_TRAITEMENT")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        r2 = self.update_status(self.commande, "PRET")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["status"], "PRET")

        r3 = self.update_status(self.commande, "LIVRE")
        self.assertEqual(r3.status_code, status.HTTP_200_OK)

    def test_direct_recu_to_pret_allowed(self):
        response = self.update_status(self.commande, "PRET")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_livrer_without_pret_forbidden(self):
        """Critère d'acceptation : impossible de livrer une commande non prête."""
        response = self.update_status(self.commande, "LIVRE")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.status, Commande.Status.RECU)

    def test_backwards_transition_forbidden(self):
        self.update_status(self.commande, "EN_TRAITEMENT")
        response = self.update_status(self.commande, "RECU")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_status_forbidden(self):
        response = self.update_status(self.commande, "RECU")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_status_forbidden(self):
        response = self.update_status(self.commande, "ANNULER")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_terminal_status_livre_is_final(self):
        self.update_status(self.commande, "PRET")
        self.update_status(self.commande, "LIVRE")

        response = self.update_status(self.commande, "EN_TRAITEMENT")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_tenant_update_returns_404(self):
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        commande_b = make_commande(self.pressing_b, client_b)

        response = self.update_status(commande_b, "PRET")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_update_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.update_status(self.commande, "PRET")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_generic_patch_is_405(self):
        """L'édition générique est fermée : seul update_status est exposé."""
        url = reverse("orders:commandes-detail", args=[self.commande.id])
        response = self.client.patch(url, {"total_price": "1.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ReceiptTests(TestCase):
    def test_receipt_contains_key_elements(self):
        pressing = Pressing.objects.create(name="Pressing Faso", phone="70 00 00 00")
        client = Client.objects.create(name="Awa", phone_number="70123456", pressing=pressing)
        commande = make_commande(pressing, client, ticket_number="TX-2609-001", total_price=Decimal("1500.00"))
        OrderItem.objects.create(
            commande=commande, clothing_type="Pantalon", quantity=1, unit_price=Decimal("1500.00")
        )

        receipt = format_receipt(commande)

        self.assertIn("Pressing Faso", receipt)
        self.assertIn("TX-2609-001", receipt)
        self.assertIn("Awa", receipt)
        self.assertIn("1 x Pantalon", receipt)
        self.assertIn("1500.00 FCFA", receipt)

    def test_receipt_exposed_in_detail_response(self):
        api = APIClient()
        pressing = Pressing.objects.create(name="Pressing P")
        employe = User.objects.create_user(
            username="70000003", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=pressing,
        )
        client_obj = Client.objects.create(name="Awa", phone_number="70123456", pressing=pressing)
        commande = make_commande(pressing, client_obj, ticket_number="TX-2609-002")
        api.force_authenticate(user=employe)

        response = api.get(reverse("orders:commandes-detail", args=[commande.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("TX-2609-002", response.data["receipt"])
