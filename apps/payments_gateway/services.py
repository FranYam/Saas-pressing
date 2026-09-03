"""Clients HTTP vers les opérateurs Mobile Money — implémentés à l'Issue #9.

Initiation de paiement (push USSD/STK), consultation de statut, vérification
de signature des webhooks. Toute la logique fragile côté opérateur vit ici :
si l'API d'Orange ou Moov change, seul ce module est impacté.
"""
