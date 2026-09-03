"""Tests notifications SMS (Issue #10) : signal PRET, passerelle (mockée ou
simulée), relances 7 jours, non-blocage des erreurs.

Secrets de test générés à l'exécution (règle anti-fuite du dépôt).
"""
import uuid
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.core.tests.utils import fake_password
from apps.notifications.models import SmsNotification
from apps.orders.models import Commande
from apps.tenants.models import Pressing

User = get_user_model()
PASSWORD = fake_password()

CONFIGURED_SMS = {
    "API_URL": "https://sms.example/api/send",
    "API_KEY": uuid.uuid4().hex,
    "SENDER_ID": "Pressing",
}
UNCONFIGURED_SMS = {"API_URL": "", "API_KEY": "", "SENDER_ID": ""}


def make_commande(pressing, client, **kwargs):
    now = timezone.now()
    defaults = {
        "date_depot": now,
        "date_retrait_prevue": now + timedelta(days=2),
        "total_price": Decimal("1000.00"),
        "ticket_number": "TX-2609-001",
    }
    defaults.update(kwargs)
    return Commande.objects.create(pressing=pressing, client=client, **defaults)


@override_settings(SMS_GATEWAY=CONFIGURED_SMS)
class ReadyNotificationSignalTests(TestCase):
    """Critère d'acceptation : passage PRET → requête d'envoi SMS effective
    avec le nom du pressing et le numéro de ticket court."""

    def setUp(self):
        self.pressing = Pressing.objects.create(name="Pressing Faso")
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.commande = make_commande(
            self.pressing,
            self.client_obj,
            ticket_number="TX-2609-042",
            status=Commande.Status.RECU,
        )

    def transition_to_pret(self):
        with patch("apps.notifications.services.http_client.post") as mocked_post:
            mocked_post.return_value.status_code = 202
            mocked_post.return_value.json.return_value = {"message_id": "SM-1"}
            from apps.orders.services import update_commande_status

            update_commande_status(commande=self.commande, new_status="PRET")
        return mocked_post

    def test_pret_triggers_sms_with_pressing_name_and_ticket(self):
        mocked_post = self.transition_to_pret()

        notification = SmsNotification.objects.get(kind=SmsNotification.Kind.READY)
        self.assertEqual(notification.status, SmsNotification.Status.SENT)
        self.assertEqual(notification.phone_number, "70123456")
        # Le message contient le nom du pressing et le ticket court.
        self.assertIn("Pressing Faso", notification.message)
        self.assertIn("TX-2609-042", notification.message)
        # La requête vers la passerelle a bien été émise.
        self.assertEqual(mocked_post.call_count, 1)
        sent = mocked_post.call_args.kwargs["json"]
        self.assertEqual(sent["to"], "70123456")
        self.assertIn("TX-2609-042", sent["message"])

    def test_non_pret_transition_does_not_send(self):
        with patch("apps.notifications.services.http_client.post") as mocked_post:
            mocked_post.return_value.status_code = 202
            mocked_post.return_value.json.return_value = {"message_id": "SM-2"}
            from apps.orders.services import update_commande_status

            update_commande_status(commande=self.commande, new_status="EN_TRAITEMENT")

        self.assertFalse(
            SmsNotification.objects.filter(kind=SmsNotification.Kind.READY).exists()
        )
        mocked_post.assert_not_called()

    def test_resaving_pret_does_not_resend(self):
        """Un simple re-save au même statut ne re-déclenche pas le SMS."""
        self.transition_to_pret()
        self.commande.save(update_fields=["updated_at"])

        self.assertEqual(
            SmsNotification.objects.filter(kind=SmsNotification.Kind.READY).count(), 1
        )

    @override_settings(SMS_GATEWAY=UNCONFIGURED_SMS)
    def test_unconfigured_gateway_simulates_without_blocking(self):
        from apps.orders.services import update_commande_status

        update_commande_status(commande=self.commande, new_status="PRET")

        notification = SmsNotification.objects.get(kind=SmsNotification.Kind.READY)
        self.assertEqual(notification.status, SmsNotification.Status.SIMULATED)
        # L'action métier n'est pas impactée : la commande est bien PRET.
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.status, Commande.Status.PRET)

    def test_gateway_failure_recorded_not_raised(self):
        """Une passerelle en panne n'empêche jamais le changement de statut."""
        from apps.orders.services import update_commande_status

        with patch(
            "apps.notifications.services.http_client.post",
            side_effect=ConnectionError("réseau coupé"),
        ):
            update_commande_status(commande=self.commande, new_status="PRET")

        notification = SmsNotification.objects.get(kind=SmsNotification.Kind.READY)
        self.assertEqual(notification.status, SmsNotification.Status.FAILED)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.status, Commande.Status.PRET)


@override_settings(SMS_GATEWAY=UNCONFIGURED_SMS)
class ReminderTests(TestCase):
    """Relance des linges prêts non retirés depuis plus de 7 jours."""

    def setUp(self):
        self.pressing = Pressing.objects.create(name="Pressing Faso")
        self.client_obj = Client.objects.create(
            name="Awa", phone_number="70123456", pressing=self.pressing
        )
        self.old_pret = make_commande(
            self.pressing,
            self.client_obj,
            ticket_number="TX-2609-101",
            status=Commande.Status.PRET,
            date_pret=timezone.now() - timedelta(days=8),
        )
        # Bruit : récent (2 j), livré, et prêt sans date.
        make_commande(
            self.pressing, self.client_obj,
            ticket_number="TX-2609-102", status=Commande.Status.PRET,
            date_pret=timezone.now() - timedelta(days=2),
        )
        make_commande(
            self.pressing, self.client_obj,
            ticket_number="TX-2609-103", status=Commande.Status.LIVRE,
            date_pret=timezone.now() - timedelta(days=10),
        )
        make_commande(
            self.pressing, self.client_obj,
            ticket_number="TX-2609-104", status=Commande.Status.PRET,
        )

    def test_reminders_target_only_old_ready_orders(self):
        from apps.notifications.tasks import send_reminders_task

        sent = send_reminders_task()

        self.assertEqual(sent, 1)
        reminder = SmsNotification.objects.get(kind=SmsNotification.Kind.REMINDER)
        self.assertEqual(reminder.commande_id, self.old_pret.id)
        self.assertIn("TX-2609-101", reminder.message)
        self.assertIn("Pressing Faso", reminder.message)

    def test_reminder_not_sent_twice(self):
        from apps.notifications.tasks import send_reminders_task

        send_reminders_task()
        second_run = send_reminders_task()

        self.assertEqual(second_run, 0)
        self.assertEqual(
            SmsNotification.objects.filter(kind=SmsNotification.Kind.REMINDER).count(), 1
        )

    def test_management_command(self):
        out = StringIO()
        call_command("send_reminders", stdout=out)

        self.assertIn("1 relance(s)", out.getvalue())
