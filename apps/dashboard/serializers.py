"""Sérialiseur dashboard : forme de la réponse summary (documentation)."""
from rest_framework import serializers


class UnclaimedOrderSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    ticket_number = serializers.CharField(read_only=True)
    client_name = serializers.CharField(read_only=True)
    client_phone = serializers.CharField(read_only=True)
    ready_since = serializers.DateTimeField(read_only=True)
    days_waiting = serializers.IntegerField(read_only=True)


class DashboardSummarySerializer(serializers.Serializer):
    """Indicateurs du jour — réservés au gérant (IsGerant)."""

    date = serializers.DateField(read_only=True)
    revenue_today = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    revenue_month = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    orders_today = serializers.IntegerField(read_only=True)
    orders_in_progress = serializers.IntegerField(read_only=True)
    orders_ready = serializers.IntegerField(read_only=True)
    outstanding_debts = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    debtors_count = serializers.IntegerField(read_only=True)
    unclaimed = UnclaimedOrderSerializer(many=True, read_only=True)
