"""Tests des services payments (Issue #8) : règlements et soldes."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.clients.models import Client
from apps.core.exceptions import BusinessRuleError
from apps.orders.models import Commande
from apps.payments.services import (
    get_client_balance,
    list_debtors,
    register_paiement,
)
from apps.tenants.models import Pressing

ZERO = Decimal("0.00")


def make_commande(pressing, client, total, **kwargs):
    now = timezone.now()
    defaults = {
        "date_depot": now,
        "date_retrait_prevue": now + timedelta(days=2),
        "ticket_number": "TX-2609-001",
    }
    defaults.update(kwargs)
    return Commande.objects.create(
        pressing=pressing, client=client, total_price=Decimal(total), **defaults
    )


class RegisterPaiementTests(TestCase):
    def setUp(self):
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.commande = make_commande(self.pressing, self.client_obj, "5000.00")

    def test_full_payment_marks_paye(self):
        paiement = register_paiement(
            commande=self.commande, amount=Decimal("5000.00"), mode="ESPECES"
        )

        self.assertEqual(paiement.status, Commande.PaymentStatus.PAYE)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.PAYE)

    def test_partial_payment_marks_partiel(self):
        paiement = register_paiement(
            commande=self.commande, amount=Decimal("2000.00"), mode="ESPECES"
        )

        self.assertEqual(paiement.status, Commande.PaymentStatus.PARTIEL)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.PARTIEL)

    def test_partial_then_completion_marks_paye(self):
        register_paiement(commande=self.commande, amount=Decimal("2000.00"), mode="ESPECES")
        paiement = register_paiement(commande=self.commande, amount=Decimal("3000.00"), mode="ESPECES")

        self.assertEqual(paiement.status, Commande.PaymentStatus.PAYE)

    def test_overpayment_rejected(self):
        with self.assertRaises(BusinessRuleError):
            register_paiement(
                commande=self.commande, amount=Decimal("6000.00"), mode="ESPECES"
            )

    def test_payment_on_paid_commande_rejected(self):
        register_paiement(commande=self.commande, amount=Decimal("5000.00"), mode="ESPECES")

        with self.assertRaises(BusinessRuleError):
            register_paiement(
                commande=self.commande, amount=Decimal("100.00"), mode="ESPECES"
            )

    def test_credit_registration_with_zero(self):
        paiement = register_paiement(
            commande=self.commande, amount=ZERO, mode="CREDIT"
        )

        self.assertEqual(paiement.status, Commande.PaymentStatus.CREDIT)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.payment_status, Commande.PaymentStatus.CREDIT)

    def test_credit_with_amount_rejected(self):
        with self.assertRaises(BusinessRuleError):
            register_paiement(
                commande=self.commande, amount=Decimal("1000.00"), mode="CREDIT"
            )

    def test_cash_with_zero_rejected(self):
        with self.assertRaises(BusinessRuleError):
            register_paiement(commande=self.commande, amount=ZERO, mode="ESPECES")


class ClientBalanceTests(TestCase):
    """Critère d'acceptation : le solde consolide TOUTES les commandes du client."""

    def setUp(self):
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        other = Client.objects.create(
            name="Boukary", phone_number="70998877", pressing=self.pressing
        )
        make_commande(self.pressing, other, "9999.00")  # bruit : autre client

    def test_credit_order_adds_to_client_debt(self):
        """Commande à crédit (0 payé) → la dette globale augmente immédiatement."""
        commande = make_commande(
            self.pressing, self.client_obj, "3000.00", ticket_number="TX-2609-002"
        )
        register_paiement(commande=commande, amount=ZERO, mode="CREDIT")

        balance = get_client_balance(self.client_obj)

        self.assertEqual(balance["total_due"], Decimal("3000.00"))
        self.assertEqual(balance["total_paid"], ZERO)
        self.assertEqual(balance["balance"], Decimal("3000.00"))
        self.assertEqual(len(balance["unpaid_commandes"]), 1)

    def test_balance_consolidates_all_commandes(self):
        commande_1 = make_commande(
            self.pressing, self.client_obj, "1000.00", ticket_number="TX-2609-003"
        )
        commande_2 = make_commande(
            self.pressing, self.client_obj, "2000.00", ticket_number="TX-2609-004"
        )
        register_paiement(commande=commande_1, amount=Decimal("500.00"), mode="ESPECES")
        register_paiement(commande=commande_2, amount=ZERO, mode="CREDIT")

        balance = get_client_balance(self.client_obj)

        self.assertEqual(balance["order_count"], 2)
        self.assertEqual(balance["total_due"], Decimal("3000.00"))
        self.assertEqual(balance["total_paid"], Decimal("500.00"))
        self.assertEqual(balance["balance"], Decimal("2500.00"))
        self.assertEqual(len(balance["unpaid_commandes"]), 2)

    def test_fully_paid_commande_not_listed_as_unpaid(self):
        commande = make_commande(
            self.pressing, self.client_obj, "1000.00", ticket_number="TX-2609-005"
        )
        register_paiement(commande=commande, amount=Decimal("1000.00"), mode="ESPECES")

        balance = get_client_balance(self.client_obj)

        self.assertEqual(balance["balance"], ZERO)
        self.assertEqual(balance["unpaid_commandes"], [])

    def test_list_debtors_only_positive_balances(self):
        """Critère d'acceptation : le gérant liste les clients endettés (> 0)."""
        dette = make_commande(
            self.pressing, self.client_obj, "4000.00", ticket_number="TX-2609-006"
        )
        register_paiement(commande=dette, amount=ZERO, mode="CREDIT")

        solde = Client.objects.create(name="Rassoul", phone_number="70445566", pressing=self.pressing)
        commande_soldee = make_commande(
            self.pressing, solde, "1500.00", ticket_number="TX-2609-007"
        )
        register_paiement(
            commande=commande_soldee, amount=Decimal("1500.00"), mode="ESPECES"
        )

        debtors = list_debtors(self.pressing)

        debtor_names = [c.name for c in debtors]
        self.assertIn("Awa", debtor_names)
        self.assertNotIn("Rassoul", debtor_names)
        awa = debtors.get(name="Awa")
        self.assertEqual(awa.balance, Decimal("4000.00"))
