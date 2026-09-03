"""Vues de réception des webhooks opérateurs — implémentées à l'Issue #9.

Endpoint public /api/v1/payments-gateway/webhook/<operator>/ avec validation
de signature, qui délègue l'enregistrement du paiement à payments/services.py.
"""
