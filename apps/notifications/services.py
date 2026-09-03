"""Passerelle SMS + construction des messages (Issue #10).

Wrapper autour de l'agrégateur local/régional : les signaux et tâches ne
parlent jamais directement à l'API externe — si l'agrégateur change, seul
ce module est impacté.

Règle critique : un échec d'envoi ne doit JAMAIS bloquer l'action métier
(changement de statut) — tout est journalisé sur la notification.
"""
import requests as http_client
from django.conf import settings

from apps.notifications.models import SmsNotification


class SMSGatewayError(Exception):
    """Erreur de communication avec la passerelle SMS."""


# ---------------------------------------------------------------------------
# Templates de messages (nom du pressing + ticket court — critère Issue #10)
# ---------------------------------------------------------------------------

def build_ready_message(commande) -> str:
    return (
        f"{commande.pressing.name} : votre linge est prêt ! "
        f"Ticket {commande.ticket_number}. Merci de venir le retirer."
    )


def build_reminder_message(commande) -> str:
    return (
        f"{commande.pressing.name} : rappel - votre linge (ticket "
        f"{commande.ticket_number}) est prêt depuis plus de 7 jours. "
        "Merci de venir le retirer."
    )


# ---------------------------------------------------------------------------
# Journalisation & envoi
# ---------------------------------------------------------------------------

def create_notification(*, commande, kind: str, message: str) -> SmsNotification:
    return SmsNotification.objects.create(
        commande=commande,
        pressing=commande.pressing,
        kind=kind,
        phone_number=commande.client.phone_number,
        message=message,
    )


def _gateway_send(*, to: str, message: str) -> dict:
    """Appel HTTP à la passerelle. URL vide = mode simulation (dev/pilote)."""
    config = settings.SMS_GATEWAY
    api_url = config.get("API_URL", "")
    if not api_url:
        return {"simulated": True, "provider_ref": ""}

    headers = {"Authorization": f"Bearer {config.get('API_KEY', '')}"}
    payload = {
        "to": to,
        "from": config.get("SENDER_ID", ""),
        "message": message,
    }
    try:
        response = http_client.post(api_url, json=payload, headers=headers, timeout=15)
    except http_client.RequestException as exc:
        raise SMSGatewayError(f"Passerelle SMS injoignable : {exc}") from exc

    if response.status_code not in (200, 201, 202):
        raise SMSGatewayError(f"Passerelle SMS HTTP {response.status_code}.")

    try:
        data = response.json()
    except ValueError as exc:
        raise SMSGatewayError("Réponse passerelle illisible (JSON invalide).") from exc

    return {"simulated": False, "provider_ref": str(data.get("message_id") or "")}


def send_notification(notification: SmsNotification) -> None:
    """Envoie une notification PENDING et journalise le résultat — sans lever.

    Filet de sécurité total : quelle que soit l'erreur (passerelle, réseau,
    imprévu), l'échec est journalisé sur la notification plutôt que
    remonté à l'appelant (le changement de statut ne doit jamais échouer
    à cause du SMS).
    """
    try:
        result = _gateway_send(to=notification.phone_number, message=notification.message)
    except Exception as exc:  # noqa: BLE001 — journaliser plutôt que lever
        notification.status = SmsNotification.Status.FAILED
        notification.error_message = str(exc)[:500]
    else:
        if result.get("simulated"):
            notification.status = SmsNotification.Status.SIMULATED
        else:
            notification.status = SmsNotification.Status.SENT
        notification.provider_ref = result.get("provider_ref", "")

    notification.save(update_fields=["status", "provider_ref", "error_message", "updated_at"])
