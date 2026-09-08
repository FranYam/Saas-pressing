"""Portail client public — accès aux commandes par ticket + téléphone.

Le client final n'a pas de compte : il présente le n° de ticket figurant
sur son reçu (papier ou SMS) accompagné de son numéro de téléphone.
La correspondance des DEUX informations ouvre l'accès à l'historique
complet de ses commandes pour le pressing émetteur du ticket.

Pas de pagination ici : un client a quelques dizaines de commandes au
maximum, on retourne la liste entière (triée par date de dépôt décroissante
comme le modèle).
"""
from django.db.models import Sum
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clients.services import normalize_phone
from apps.orders.models import Commande
from apps.orders.serializers import CommandeSerializer


def _last_8_digits(phone: str) -> str:
    """8 derniers chiffres — robuste aux formats « 70123456 » et « 22670123456 »."""
    digits = normalize_phone(phone)
    return digits[-8:] if len(digits) >= 8 else digits


class ClientPortalView(APIView):
    """GET /api/v1/portal/orders/?ticket=PR-0001&phone=+226 70 12 34 56

    - 200 : fiche client + commandes (avec montant déjà payé par commande)
    - 400 : paramètres manquants
    - 404 : couple ticket/téléphone inconnu — message volontairement générique
             pour ne divulguer ni l'existence d'un ticket, ni celle d'un numéro.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # publique : aucun header Authorization requis

    @extend_schema(
        operation_id="portal_orders",
        description=(
            "Accès client public : valide le couple (n° de ticket, téléphone) "
            "et retourne la fiche client avec toutes ses commandes."
        ),
        responses={200: dict},
    )
    def get(self, request):
        ticket = (request.query_params.get("ticket") or "").strip()
        phone = (request.query_params.get("phone") or "").strip()
        if not ticket or not phone:
            return Response(
                {"detail": "Les paramètres ticket et phone sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1) Le ticket désigne une commande (et donc son pressing et son client).
        commande = (
            Commande.objects.select_related("client", "pressing")
            .filter(ticket_number__iexact=ticket)
            .first()
        )
        # Comparaison sur les 8 derniers chiffres : la base peut contenir le
        # numéro au format local (70123456) ou E.164 (22670123456).
        if commande is None or _last_8_digits(
            commande.client.phone_number
        ) != _last_8_digits(phone):
            return Response(
                {"detail": "Ticket introuvable. Vérifiez le numéro de ticket et le téléphone."},
                status=status.HTTP_404_NOT_FOUND,
            )

        client = commande.client
        commandes = (
            Commande.objects.filter(client=client)
            .select_related("client", "pressing", "assigned_courier")
            .prefetch_related("articles")
        )

        # Montant réellement encaissé par commande (les écritures « crédit »
        # ont amount=0, la somme est donc l'encaissé net).
        from apps.payments.models import Paiement  # import local : évite le cycle

        paye_par_commande = dict(
            Paiement.objects.filter(commande__in=commandes)
            .values_list("commande")
            .annotate(total=Sum("amount"))
        )

        serializer = CommandeSerializer(commandes, many=True)
        orders = []
        for data, cmd in zip(serializer.data, commandes):
            data["amount_paid"] = str(paye_par_commande.get(cmd.id, 0))
            orders.append(data)

        return Response(
            {
                "name": client.name,
                "phone": client.phone_number,
                "pressing": commande.pressing.name,
                "orders": orders,
            }
        )
