"""Tests du tableau de bord gérant (Issue #12).

Jeu de données déterministe (pressing A) :
- c1 client A : total 5000, payée aujourd'hui (ESPECES), statut RECU
- c2 client B : total 3000, acompte 2000 aujourd'hui, statut EN_TRAITEMENT
- c3 client C : total 4000, à crédit (0 payé), PRET depuis 10 jours
- c4 client A : total 1000, payée le mois DERNIER, statut LIVRE
→ Attentes : CA jour 7000, CA mois 7000, créances 5000, débiteurs 2,
  commandes du jour 2, en cours 3, prêtes 1, non réclamées [c3].
"""
from datetime import datetime, time, timedelta
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
from apps.payments.models import Paiement
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()


def make_client(pressing, name, phone):
    return Client.objects.create(name=name, phone_number=phone, pressing=pressing)


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


class DashboardSummaryTests(TestCase):
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
        self.coursier = User.objects.create_user(
            username="70000003", password=PASSWORD,
            role=User.Role.COURSIER, pressing=self.pressing_a,
        )

        now = timezone.now()
        client_a = make_client(self.pressing_a, "Awa", "70123456")
        client_b = make_client(self.pressing_a, "Boukary", "70223344")
        client_c = make_client(self.pressing_a, "Clarisse", "70334455")

        # c1 : payée aujourd'hui (CA jour), linge encore en traitement.
        c1 = make_commande(
            self.pressing_a, client_a, "5000.00",
            status=Commande.Status.RECU, ticket_number="TX-2609-001",
        )
        Paiement.objects.create(
            commande=c1, amount=Decimal("5000.00"), mode="ESPECES",
            status="PAYE", pressing=self.pressing_a,
        )

        # c2 : acompte aujourd'hui → débitrice de 1000.
        c2 = make_commande(
            self.pressing_a, client_b, "3000.00",
            status=Commande.Status.EN_TRAITEMENT, ticket_number="TX-2609-002",
        )
        Paiement.objects.create(
            commande=c2, amount=Decimal("2000.00"), mode="ESPECES",
            status="PARTIEL", pressing=self.pressing_a,
        )

        # c3 : à crédit, prête depuis 10 jours → non réclamée.
        c3 = make_commande(
            self.pressing_a, client_c, "4000.00",
            status=Commande.Status.PRET, ticket_number="TX-2609-003",
            date_depot=now - timedelta(days=12),
            date_pret=now - timedelta(days=10),
        )
        Paiement.objects.create(
            commande=c3, amount=Decimal("0.00"), mode="CREDIT",
            status="CREDIT", pressing=self.pressing_a,
        )

        # c4 : payée le mois dernier, livrée → hors CA mois, hors « en cours ».
        last_month_end = now.date().replace(day=1) - timedelta(days=1)
        c4 = make_commande(
            self.pressing_a, client_a, "1000.00",
            status=Commande.Status.LIVRE, ticket_number="TX-2609-004",
            date_depot=now - timedelta(days=40),
        )
        Paiement.objects.create(
            commande=c4, amount=Decimal("1000.00"), mode="ESPECES",
            status="PAYE", pressing=self.pressing_a,
            date_paiement=timezone.make_aware(
                datetime.combine(last_month_end, time(12, 0))
            ),
        )

        # Bruit : le pressing B ne doit JAMAIS apparaître chez A.
        client_b2 = make_client(self.pressing_b, "Espion", "70999000")
        commande_b = make_commande(
            self.pressing_b, client_b2, "99999.00",
            status=Commande.Status.PRET, ticket_number="TX-2609-900",
            date_depot=now, date_pret=now - timedelta(days=15),
        )
        Paiement.objects.create(
            commande=commande_b, amount=Decimal("99999.00"), mode="ESPECES",
            status="PAYE", pressing=self.pressing_b,
        )

        self.url = reverse("dashboard:summary")

    # ------------------------------------------------------------- contenu

    def test_gerant_gets_consolidated_summary(self):
        self.client.force_authenticate(user=self.gerant)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(Decimal(str(data["revenue_today"])), Decimal("7000.00"))
        self.assertEqual(Decimal(str(data["revenue_month"])), Decimal("7000.00"))
        self.assertEqual(Decimal(str(data["outstanding_debts"])), Decimal("5000.00"))
        self.assertEqual(data["debtors_count"], 2)
        self.assertEqual(data["orders_today"], 2)
        self.assertEqual(data["orders_in_progress"], 3)  # c1, c2, c3 (c4 livrée)
        self.assertEqual(data["orders_ready"], 1)
        self.assertEqual(len(data["unclaimed"]), 1)
        self.assertEqual(data["unclaimed"][0]["ticket_number"], "TX-2609-003")
        self.assertEqual(data["unclaimed"][0]["client_name"], "Clarisse")
        self.assertGreaterEqual(data["unclaimed"][0]["days_waiting"], 10)

    def test_revenue_today_is_tenant_scoped(self):
        """Le CA du jour du pressing B (99999) ne fuit jamais chez A."""
        self.client.force_authenticate(user=self.gerant)

        response = self.client.get(self.url)

        self.assertEqual(Decimal(str(response.data["revenue_today"])), Decimal("7000.00"))
        self.assertEqual(len(response.data["unclaimed"]), 1)  # pas la commande B

    # ------------------------------------------------------------ sécurité

    def test_employee_forbidden(self):
        """Critère d'acceptation : les stats financières sont invisibles des employés."""
        self.client.force_authenticate(user=self.employe)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_coursier_forbidden(self):
        self.client.force_authenticate(user=self.coursier)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
