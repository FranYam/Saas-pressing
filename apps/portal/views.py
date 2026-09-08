"""Portail client public — comptes clients, catalogue et demandes de collecte.

Deux modes d'accès cohabitent :
1. **Compte client** (téléphone + mot de passe) : inscription, connexion,
   consultation du catalogue et initiation de collectes en ligne ;
2. **Accès rapide par ticket** : le n° de ticket du reçu + le téléphone
   suffisent pour consulter ses commandes (aucun compte requis).

Le jeton de session (`X-Portal-Token`) est régénéré à chaque connexion et
révoqué à la déconnexion — il vaut pour un seul client, tous pressings.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import make_password
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Tarif
from apps.clients.models import Client
from apps.clients.services import (
    clean_phone,
    issue_portal_token,
    verify_client_password,
)
from apps.orders.models import Commande
from apps.orders.serializers import CommandeSerializer
from apps.orders.services import create_commande
from apps.tenants.models import Pressing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def client_from_token(request):
    """Résout le client depuis l'en-tête X-Portal-Token (None si invalide)."""
    token = (request.headers.get("X-Portal-Token") or "").strip()
    if not token:
        return None
    return Client.objects.filter(portal_token=token).select_related("pressing").first()


def _client_payload(client: Client) -> dict:
    """Fiche + commandes du client (montant déjà payé par commande)."""
    from apps.payments.models import Paiement  # import local : évite le cycle

    commandes = (
        Commande.objects.filter(client=client)
        .select_related("client", "pressing", "assigned_courier")
        .prefetch_related("articles")
    )
    paye_par_commande = dict(
        Paiement.objects.filter(commande__in=commandes)
        .values_list("commande")
        .annotate(total=Sum("amount"))
    )
    orders = []
    for data, cmd in zip(CommandeSerializer(commandes, many=True).data, commandes):
        data["amount_paid"] = str(paye_par_commande.get(cmd.id, 0))
        orders.append(data)
    return {
        "name": client.name,
        "phone": client.phone_number,
        "pressing": client.pressing.name,
        "pressing_id": client.pressing_id,
        "orders": orders,
    }


def _last_8_digits(phone: str) -> str:
    """8 derniers chiffres — robuste aux formats « 70123456 » et « 22670123456 »."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits[-8:] if len(digits) >= 8 else digits


# ---------------------------------------------------------------------------
# Pressings + inscription + connexion
# ---------------------------------------------------------------------------

class PressingListView(APIView):
    """Liste publique des pressings — sert au choix du pressing à l'inscription."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            [{"id": p.id, "name": p.name, "phone": p.phone} for p in Pressing.objects.all()]
        )


class ClientRegisterView(APIView):
    """POST /portal/register/ — {pressing, name, phone, password}.

    Si une fiche existe déjà pour ce (téléphone, pressing) — créée au
    comptoir — elle est promue en compte client : le client conserve son
    historique. Sinon une nouvelle fiche est créée.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        pressing_id = request.data.get("pressing")
        name = (request.data.get("name") or "").strip()
        password = (request.data.get("password") or "")
        try:
            phone = clean_phone(request.data.get("phone") or "")
        except Exception:
            return Response({"detail": "Numéro de téléphone invalide."}, status=400)

        if not name or len(password) < 6:
            return Response(
                {"detail": "Nom et mot de passe (6 caractères min.) sont requis."},
                status=400,
            )
        try:
            pressing = Pressing.objects.get(pk=pressing_id)
        except Pressing.DoesNotExist:
            return Response({"detail": "Pressing introuvable."}, status=400)

        client = Client.objects.filter(phone_number=phone, pressing=pressing).first()
        if client:
            if client.password:
                return Response(
                    {"detail": "Un compte existe déjà avec ce numéro. Connectez-vous."},
                    status=409,
                )
            client.name = name or client.name
        else:
            client = Client(name=name, phone_number=phone, pressing=pressing)
        client.password = make_password(password)
        client.save()

        token = issue_portal_token(client)
        return Response({"token": token, **_client_payload(client)}, status=201)


class ClientLoginView(APIView):
    """POST /portal/login/ — {phone, password} → jeton + commandes."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get("phone") or ""
        password = request.data.get("password") or ""

        # Le téléphone suffit à identifier : unicité par pressing, mais un
        # même numéro dans deux pressings partage... non — on essaie chaque
        # fiche correspondante et on valide le mot de passe.
        for client in Client.objects.filter(phone_number__in=[
            phone, _last_8_digits(phone), f"226{_last_8_digits(phone)}"
        ]).select_related("pressing"):
            if verify_client_password(client, password):
                token = issue_portal_token(client)
                return Response({"token": token, **_client_payload(client)})

        return Response(
            {"detail": "Téléphone ou mot de passe incorrect."},
            status=401,
        )


class ClientMeView(APIView):
    """GET /portal/me/ (X-Portal-Token) — session courante + commandes."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        client = client_from_token(request)
        if not client:
            return Response({"detail": "Session expirée — reconnectez-vous."}, status=401)
        return Response(_client_payload(client))

    def delete(self, request):
        """Déconnexion : révoque le jeton."""
        client = client_from_token(request)
        if client:
            client.portal_token = ""
            client.save(update_fields=["portal_token", "updated_at"])
        return Response(status=204)


# ---------------------------------------------------------------------------
# Catalogue + demandes de collecte
# ---------------------------------------------------------------------------

class PortalCatalogView(APIView):
    """GET /portal/catalog/ — tarifs actifs du pressing du client connecté."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        client = client_from_token(request)
        pressing = client.pressing if client else None
        pressing_id = pressing.id if pressing else request.query_params.get("pressing")
        if not pressing_id:
            return Response({"detail": "Session ou paramètre pressing requis."}, status=400)
        tarifs = Tarif.objects.filter(pressing_id=pressing_id, is_active=True)
        return Response(
            [
                {"id": t.id, "name": t.name, "category": t.category, "price": str(t.price)}
                for t in tarifs
            ]
        )


class PortalCollecteView(APIView):
    """POST /portal/collectes/ (X-Portal-Token) — initie une collecte à domicile.

    Crée une vraie commande (canal EN_LIGNE, livraison À_COLLECTER) avec
    ticket généré. Les prix sont TOUJOURS repris du catalogue côté serveur.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        client = client_from_token(request)
        if not client:
            return Response({"detail": "Session expirée — reconnectez-vous."}, status=401)

        address = (request.data.get("collect_address") or "").strip()
        slot = (request.data.get("creneau") or "").strip()
        notes = (request.data.get("notes") or "").strip()
        items = request.data.get("articles") or []
        if not address:
            return Response({"detail": "L'adresse de collecte est requise."}, status=400)
        if not items:
            return Response({"detail": "Sélectionnez au moins un article."}, status=400)

        # Chiffrement serveur depuis le catalogue du pressing.
        tarifs = {t.name: t for t in Tarif.objects.filter(pressing=client.pressing, is_active=True)}
        articles = []
        for item in items:
            tarif = tarifs.get((item.get("clothing_type") or "").strip())
            if not tarif:
                return Response(
                    {"detail": f"« {item.get('clothing_type')} » n'est pas au catalogue."},
                    status=400,
                )
            try:
                quantity = int(item.get("quantity"))
            except (TypeError, ValueError):
                quantity = 0
            if not 1 <= quantity <= 50:
                return Response(
                    {"detail": f"Quantité invalide pour « {tarif.name} » (1 à 50)."},
                    status=400,
                )
            articles.append(
                {"clothing_type": tarif.name, "quantity": quantity, "unit_price": tarif.price}
            )

        commande = create_commande(
            pressing=client.pressing,
            client=client,
            articles=articles,
            date_retrait_prevue=timezone.now() + timedelta(days=3),
            canal=Commande.Canal.EN_LIGNE,
        )
        # Cycle logistique : la marchandise est à aller chercher chez le client.
        commande.delivery_status = Commande.DeliveryStatus.A_COLLECTER
        # Le créneau et les notes n'ont pas de champ dédié : concaténés à
        # l'adresse, visibles par le coursier et le comptoir.
        parts = [address]
        if slot:
            parts.append(f"Créneau : {slot}")
        if notes:
            parts.append(f"Note : {notes}")
        commande.collect_address = " — ".join(parts)
        commande.save(update_fields=["delivery_status", "collect_address", "updated_at"])

        data = CommandeSerializer(commande).data
        return Response(data, status=201)


# ---------------------------------------------------------------------------
# Accès rapide par ticket (existant)
# ---------------------------------------------------------------------------

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

        return Response(_client_payload(commande.client))
