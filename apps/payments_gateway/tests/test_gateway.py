"""Tests payments_gateway (Issue #9) : initiation (HTTP mocké), webhook signé
HMAC, idempotence, délégation sécurisée à payments/services.

Secrets de test générés à l'exécution — aucun littéral dans le dépôt
(règle anti-fuite, voir apps/core/tests/utils.py).
"""
import hashlib
import hmac
import json
import uuid
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.orders.models import Commande
from apps.payments.models import Paiement
from apps.payments_gateway.models import MobileMoneyRequest
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()
WEBHOOK_SECRET = uuid.uuid4().hex  # secret factice généré à l'exécution

GATEWAY_SETTINGS = {
    "ORANGE": {
        "API_URL": "https://orange.example/api/push",
        "API_KEY": uuid.uuid4().hex,
        "WEBHOOK_SECRET": WEBHOOK_SECRET,
    },
    "MOOV": {
        "API_URL": "https://moov.example/api/push",
        "API_KEY": uuid.uuid4().hex,
        "WEBHOOK_SECRET": uuid.uuid4().hex,
    },
}

UNCONFIGURED_SETTINGS = {  # aucune URL : l'initiation doit échouer proprement
    "ORANGE": {"API_URL": "", "API_KEY": "", "WEBHOOK_SECRET": WEBHOOK_SECRET},
}


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


@contextmanager
def mock_operator_response(reference="OP-12345"):
    """Réponse simulée d'un opérateur (succès) — aucun vrai appel HTTP."""
    with patch("apps.payments_gateway.services.http_client.post") as mocked_post:
        mocked_post.return_value.status_code = 202
        mocked_post.return_value.json.return_value = {"transaction_id": reference}
        yield mocked_post


def signed_webhook_post(api_client, url, payload, secret=WEBHOOK_SECRET):
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return api_client.post(
        url, data=body, content_type="application/json", HTTP_X_SIGNATURE=signature
    )


@override_settings(MOBILE_MONEY=GATEWAY_SETTINGS)
class InitiatePaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.commande = make_commande(
            self.pressing, self.client_obj, "5000.00", ticket_number="TX-2609-001"
        )
        self.initiate_url = reverse("payments_gateway:initiate")
        self.client.force_authenticate(user=self.employe)

    def test_initiate_sends_request_to_operator(self):
        """Critère d'acceptation : l'initiation déclenche la requête externe."""
        with mock_operator_response() as mocked_post:
            response = self.client.post(
                self.initiate_url,
                {
                    "commande": str(self.commande.id),
                    "phone_number": "70 12 34 56",
                    "operator": "ORANGE",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], MobileMoneyRequest.Status.PENDING)
        self.assertEqual(response.data["amount"], "5000.00")
        self.assertEqual(response.data["provider_ref"], "OP-12345")
        # La requête vers l'opérateur a bien été émise avec le bon payload.
        self.assertEqual(mocked_post.call_count, 1)
        sent_payload = mocked_post.call_args.kwargs["json"]
        self.assertEqual(sent_payload["phone"], "70123456")  # normalisé
        self.assertEqual(sent_payload["amount"], "5000.00")
        self.assertEqual(sent_payload["currency"], "XOF")

    def test_initiate_amount_is_remaining_not_payload(self):
        Paiement.objects.create(
            commande=self.commande, amount=Decimal("2000.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing,
        )

        with mock_operator_response():
            response = self.client.post(
                self.initiate_url,
                {
                    "commande": str(self.commande.id),
                    "phone_number": "70123456",
                    "operator": "MOOV",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "3000.00")  # reste à payer

    @override_settings(MOBILE_MONEY=UNCONFIGURED_SETTINGS)
    def test_initiate_without_config_fails_cleanly(self):
        response = self.client.post(
            self.initiate_url,
            {
                "commande": str(self.commande.id),
                "phone_number": "70123456",
                "operator": "ORANGE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mm_request = MobileMoneyRequest.objects.get()
        self.assertEqual(mm_request.status, MobileMoneyRequest.Status.FAILED)
        self.assertEqual(Paiement.objects.count(), 0)  # aucune écriture financière

    def test_initiate_on_paid_commande_rejected(self):
        Paiement.objects.create(
            commande=self.commande, amount=Decimal("5000.00"), mode="ESPECES",
            status="PAYE", pressing=self.pressing,
        )
        self.commande.payment_status = Commande.PaymentStatus.PAYE
        self.commande.save()

        response = self.client.post(
            self.initiate_url,
            {
                "commande": str(self.commande.id),
                "phone_number": "70123456",
                "operator": "ORANGE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_initiate_cross_tenant_commande_404(self):
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        commande_b = make_commande(
            self.pressing_b, client_b, "2000.00", ticket_number="TX-2609-002"
        )

        response = self.client.post(
            self.initiate_url,
            {
                "commande": str(commande_b.id),
                "phone_number": "70998877",
                "operator": "ORANGE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_initiate_unauthenticated_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self.initiate_url,
            {"commande": str(self.commande.id), "phone_number": "70123456", "operator": "ORANGE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MOBILE_MONEY=GATEWAY_SETTINGS)
class WebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.commande = make_commande(
            self.pressing, self.client_obj, "5000.00", ticket_number="TX-2609-010"
        )
        self.mm_request = MobileMoneyRequest.objects.create(
            commande=self.commande,
            pressing=self.pressing,
            operator="ORANGE",
            phone_number="70123456",
            amount=Decimal("5000.00"),
            provider_ref="OP-WEBHOOK-1",
        )
        self.webhook_url = reverse("payments_gateway:webhook", args=["orange"])

    def test_valid_webhook_marks_commande_paid(self):
        """Critère d'acceptation : le webhook valide marque la commande Payée."""
        response = signed_webhook_post(
            self.client,
            self.webhook_url,
            {"reference": "OP-WEBHOOK-1", "status": "SUCCESS", "amount": "5000.00"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.PAYE)
        paiement = Paiement.objects.get(commande=self.commande)
        self.assertEqual(paiement.mode, "MOBILE_MONEY")
        self.assertEqual(paiement.amount, Decimal("5000.00"))
        self.mm_request.refresh_from_db()
        self.assertEqual(self.mm_request.status, MobileMoneyRequest.Status.CONFIRMED)

    def test_webhook_is_idempotent(self):
        """Un webhook rejoué ne crée jamais un double paiement."""
        payload = {"reference": "OP-WEBHOOK-1", "status": "SUCCESS", "amount": "5000.00"}
        first = signed_webhook_post(self.client, self.webhook_url, payload)
        second = signed_webhook_post(self.client, self.webhook_url, payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "already_processed")
        self.assertEqual(Paiement.objects.filter(commande=self.commande).count(), 1)

    def test_webhook_invalid_signature_403(self):
        body = json.dumps(
            {"reference": "OP-WEBHOOK-1", "status": "SUCCESS"}
        ).encode("utf-8")

        response = self.client.post(
            self.webhook_url,
            data=body,
            content_type="application/json",
            HTTP_X_SIGNATURE="deadbeef" * 8,  # signature falsifiée
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_webhook_without_signature_403(self):
        response = self.client.post(
            self.webhook_url,
            {"reference": "OP-WEBHOOK-1", "status": "SUCCESS"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_webhook_amount_mismatch_rejected(self):
        """Garde anti-fraude : montant annoncé ≠ montant demandé."""
        response = signed_webhook_post(
            self.client,
            self.webhook_url,
            {"reference": "OP-WEBHOOK-1", "status": "SUCCESS", "amount": "100.00"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_webhook_failure_event_recorded(self):
        response = signed_webhook_post(
            self.client,
            self.webhook_url,
            {"reference": "OP-WEBHOOK-1", "status": "FAILED", "message": "Client injoignable"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mm_request.refresh_from_db()
        self.assertEqual(self.mm_request.status, MobileMoneyRequest.Status.FAILED)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_webhook_unknown_reference_404(self):
        response = signed_webhook_post(
            self.client,
            self.webhook_url,
            {"reference": "INCONNU", "status": "SUCCESS"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_webhook_unknown_operator_404(self):
        url = reverse("payments_gateway:webhook", args=["telecel"])
        response = signed_webhook_post(
            self.client, url, {"reference": "X", "status": "SUCCESS"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_webhook_invalid_payload_400(self):
        response = signed_webhook_post(self.client, self.webhook_url, {"foo": "bar"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_reference_by_uuid(self):
        """La référence peut être notre UUID interne ou la référence opérateur."""
        response = signed_webhook_post(
            self.client,
            self.webhook_url,
            {"reference": str(self.mm_request.id), "status": "SUCCESS"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.PAYE)


class RequestsListViewTests(TestCase):
    """Suivi tenant-scopé des demandes Mobile Money."""

    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.pressing_b = Pressing.objects.create(name="Pressing B")
        self.employe = User.objects.create_user(
            username="70000002", password=PASSWORD,
            role=User.Role.EMPLOYE, pressing=self.pressing,
        )
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        commande = make_commande(
            self.pressing, self.client_obj, "1000.00", ticket_number="TX-2609-020"
        )
        self.list_url = reverse("payments_gateway:requests-list")

        MobileMoneyRequest.objects.create(
            commande=commande, pressing=self.pressing, operator="MOOV",
            phone_number="70123456", amount=Decimal("1000.00"),
        )
        # Bruit : demande du pressing B — jamais visible pour A
        client_b = Client.objects.create(name="B", phone_number="70998877", pressing=self.pressing_b)
        commande_b = make_commande(
            self.pressing_b, client_b, "2000.00", ticket_number="TX-2609-021"
        )
        MobileMoneyRequest.objects.create(
            commande=commande_b, pressing=self.pressing_b, operator="ORANGE",
            phone_number="70998877", amount=Decimal("2000.00"),
        )
        self.client.force_authenticate(user=self.employe)

    def test_list_is_tenant_scoped(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        operators = {r["operator"] for r in response.data["results"]}
        self.assertEqual(operators, {"MOOV"})

    def test_unauthenticated_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
