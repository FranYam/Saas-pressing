"""Webhooks opérateurs — réception des confirmations Mobile Money (Issue #9).

Endpoint PUBLIC (pas de JWT) : l'authenticité est garantie par la signature
HMAC-SHA256 du corps brut, calculée avec le secret partagé de l'opérateur
(settings.MOBILE_MONEY[<operator>]["WEBHOOK_SECRET"]).
"""
import hashlib
import hmac
import json
import secrets as crypto_secrets

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments_gateway.services import process_webhook


def verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 du corps brut, comparaison à temps constant."""
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    return bool(provided) and crypto_secrets.compare_digest(provided, expected)


class OperatorWebhookView(APIView):
    """POST /api/v1/payments-gateway/webhook/<operator>/ — public, signé."""

    permission_classes = [AllowAny]
    authentication_classes = []  # webhook : aucun mécanisme d'auth utilisateur

    @extend_schema(
        request=inline_serializer(
            name="MobileMoneyWebhook",
            fields={
                "reference": serializers.CharField(help_text="Référence opérateur ou UUID de la demande"),
                "status": serializers.ChoiceField(choices=["SUCCESS", "FAILED"]),
                "amount": serializers.CharField(required=False),
                "message": serializers.CharField(required=False),
            },
        ),
        responses={200: None, 400: None, 403: None, 404: None},
        description=(
            "Callback opérateur : corps signé HMAC-SHA256 (en-tête X-Signature, "
            "secret partagé par opérateur). Idempotent — un webhook rejoué ne "
            "crée pas de double paiement."
        ),
    )
    def post(self, request, operator):
        operator = operator.strip().upper()
        config = settings.MOBILE_MONEY.get(operator)
        if config is None:
            return Response(
                {"detail": "Opérateur inconnu."}, status=http_status.HTTP_404_NOT_FOUND
            )

        secret = config.get("WEBHOOK_SECRET", "")
        if not secret:
            return Response(
                {"detail": "Webhook non configuré pour cet opérateur."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        signature = request.headers.get("X-Signature", "")
        if not verify_signature(secret, request.body, signature):
            return Response(
                {"detail": "Signature invalide."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return Response(
                {"detail": "Corps JSON invalide."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(payload, dict):
            return Response(
                {"detail": "Payload JSON objet attendu."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        status_code, data = process_webhook(operator=operator, payload=payload)
        return Response(data, status=status_code)
