"""Vue dashboard : GET /api/v1/dashboard/summary/ — gérant uniquement (Issue #12).

Les statistiques financières ne sont JAMAIS accessibles aux employés ni
aux coursiers (critère d'acceptation).
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsGerant
from apps.dashboard.serializers import DashboardSummarySerializer
from apps.dashboard.services import get_summary


class DashboardSummaryView(APIView):
    """Indicateurs temps réel du pressing connecté (gérant)."""

    permission_classes = [IsAuthenticated, IsGerant]

    @extend_schema(
        responses={200: DashboardSummarySerializer},
        description=(
            "Agrégats du jour : chiffre d'affaires (jour/mois) consolidé depuis "
            "tous les paiements, commandes en cours, encours des créances, "
            "nombre de clients débiteurs et linges prêts non réclamés (> 7 jours)."
        ),
    )
    def get(self, request):
        summary = get_summary(request.user.pressing)
        return Response(DashboardSummarySerializer(summary).data)
