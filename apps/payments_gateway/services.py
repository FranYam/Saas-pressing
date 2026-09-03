"""Logique payments_gateway — clients opérateur, initiation, traitement webhook.

Toute la fragilité côté opérateurs (HTTP, formats, signatures) vit ici.
Si l'API d'Orange ou Moov change, seul ce module est impacté. Les écritures
financières restent déléguées à `apps.payments.services`.
"""
from decimal import Decimal
from uuid import UUID

import requests as http_client
from django.conf import settings
from django.db import transaction

from apps.core.exceptions import BusinessRuleError
from apps.orders.models import Commande
from apps.payments.services import get_commande_paid_amount, register_paiement
from apps.payments_gateway.models import MobileMoneyRequest


class GatewayError(Exception):
    """Erreur lors de la communication avec un opérateur Mobile Money."""


# ---------------------------------------------------------------------------
# Clients opérateurs — pilotés par settings.MOBILE_MONEY (valeurs .env)
# ---------------------------------------------------------------------------

class OperatorClient:
    """Client HTTP générique d'initiation de push USSD/STK."""

    operator_id = ""

    def __init__(self, config: dict):
        self.config = config

    def initiate(self, *, phone: str, amount, reference: str) -> dict:
        api_url = self.config.get("API_URL", "")
        if not api_url:
            raise GatewayError("Opérateur non configuré : URL d'API absente.")

        payload = {
            "operator": self.operator_id,
            "phone": phone,
            "amount": str(amount),
            "currency": "XOF",
            "reference": reference,
            "callback_url": f"{api_url.rstrip('/').rsplit('/api', 1)[0]}"
            "/api/v1/payments-gateway/webhook/"
            f"{self.operator_id.lower()}/",
        }
        headers = {"Authorization": f"Bearer {self.config.get('API_KEY', '')}"}

        try:
            response = http_client.post(api_url, json=payload, headers=headers, timeout=15)
        except http_client.RequestException as exc:
            raise GatewayError(f"Opérateur injoignable : {exc}") from exc

        if response.status_code not in (200, 201, 202):
            raise GatewayError(f"Opérateur a répondu HTTP {response.status_code}.")

        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayError("Réponse opérateur illisible (JSON invalide).") from exc

        return {"provider_ref": str(data.get("transaction_id") or data.get("id") or "")}


class OrangeMoneyClient(OperatorClient):
    operator_id = MobileMoneyRequest.Operator.ORANGE


class MoovMoneyClient(OperatorClient):
    operator_id = MobileMoneyRequest.Operator.MOOV


OPERATOR_CLIENTS = {
    MobileMoneyRequest.Operator.ORANGE: OrangeMoneyClient,
    MobileMoneyRequest.Operator.MOOV: MoovMoneyClient,
}


def get_operator_client(operator: str):
    """Construit le client depuis la config settings (surchargeable en tests)."""
    config = settings.MOBILE_MONEY.get(operator, {})
    client_cls = OPERATOR_CLIENTS.get(operator)
    if client_cls is None:
        return None
    return client_cls(config)


# ---------------------------------------------------------------------------
# Initiation — déclenchée au comptoir (ou plus tard en ligne)
# ---------------------------------------------------------------------------

def initiate_mobile_money_payment(
    *, commande: Commande, phone_number: str, operator: str
) -> MobileMoneyRequest:
    """
    Déclenche un push Mobile Money pour le RESTE À PAYER de la commande.

    Le montant est calculé serveur (jamais depuis le payload). En cas
    d'échec opérateur, la demande est archivée FAILED avec le motif —
    aucune écriture financière n'a lieu. Volontairement SANS transaction
    englobante : l'archive FAILED doit survivre à l'exception remontée
    à l'appelant (piste d'audit).
    """
    if commande.payment_status == Commande.PaymentStatus.PAYE:
        raise BusinessRuleError("Cette commande est déjà entièrement payée.")

    remaining = commande.total_price - get_commande_paid_amount(commande)
    if remaining <= Decimal("0.00"):
        raise BusinessRuleError("Aucun reste à payer sur cette commande.")

    client = get_operator_client(operator)
    if client is None:
        raise BusinessRuleError(f"Opérateur inconnu : {operator}.")

    mm_request = MobileMoneyRequest.objects.create(
        commande=commande,
        pressing=commande.pressing,
        operator=operator,
        phone_number=phone_number,
        amount=remaining,
    )

    try:
        result = client.initiate(
            phone=phone_number, amount=remaining, reference=str(mm_request.id)
        )
    except GatewayError as exc:
        mm_request.status = MobileMoneyRequest.Status.FAILED
        mm_request.error_message = str(exc)
        mm_request.save(update_fields=["status", "error_message", "updated_at"])
        raise BusinessRuleError(f"Échec d'initiation {operator} : {exc}") from exc

    mm_request.provider_ref = result["provider_ref"]
    mm_request.save(update_fields=["provider_ref", "updated_at"])
    return mm_request


# ---------------------------------------------------------------------------
# Webhook — confirmation asynchrone de l'opérateur (signature vérifiée en amont)
# ---------------------------------------------------------------------------

@transaction.atomic
def process_webhook(*, operator: str, payload: dict) -> tuple[int, dict]:
    """
    Traite une confirmation signée. Idempotent : un webhook rejoué (les
    opérateurs réessaient) ne crée jamais un double paiement.

    Retourne (status_code, données de réponse).
    """
    reference = str(payload.get("reference") or "").strip()
    event_status = str(payload.get("status") or "").strip().upper()

    if not reference or event_status not in ("SUCCESS", "FAILED"):
        return 400, {"detail": "Payload invalide : reference et status (SUCCESS|FAILED) requis."}

    query = MobileMoneyRequest.objects.filter(provider_ref=reference)
    try:  # la référence peut aussi être notre UUID interne
        query |= MobileMoneyRequest.objects.filter(id=UUID(reference))
    except (ValueError, AttributeError):
        pass
    mm_request = query.first()
    if mm_request is None:
        return 404, {"detail": "Demande Mobile Money introuvable."}

    if mm_request.status == MobileMoneyRequest.Status.CONFIRMED:
        return 200, {"status": "already_processed"}  # idempotence

    # Garde anti-fraude : le montant annoncé doit correspondre à la demande.
    declared_amount = payload.get("amount")
    if declared_amount is not None and Decimal(str(declared_amount)) != mm_request.amount:
        return 400, {"detail": "Montant annoncé différent du montant demandé."}

    if event_status == "FAILED":
        mm_request.status = MobileMoneyRequest.Status.FAILED
        mm_request.error_message = str(payload.get("message", ""))[:500]
        mm_request.save(update_fields=["status", "error_message", "updated_at"])
        return 200, {"status": "failed_recorded"}

    # SUCCESS → écriture financière via la logique métier de payments/.
    try:
        register_paiement(
            commande=mm_request.commande,
            amount=mm_request.amount,
            mode="MOBILE_MONEY",
        )
    except BusinessRuleError as exc:
        mm_request.status = MobileMoneyRequest.Status.FAILED
        mm_request.error_message = str(exc)
        mm_request.save(update_fields=["status", "error_message", "updated_at"])
        return 409, {"detail": str(exc)}

    mm_request.status = MobileMoneyRequest.Status.CONFIRMED
    mm_request.save(update_fields=["status", "updated_at"])
    return 200, {
        "status": "confirmed",
        "commande": str(mm_request.commande_id),
        "payment_status": mm_request.commande.payment_status,
    }
