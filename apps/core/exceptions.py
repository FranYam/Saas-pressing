"""Exceptions métier partagées.

Les `services.py` des apps métier lèvent `BusinessRuleError` quand une règle
métier est violée (ex. transition de statut interdite sur une commande).
DRF la convertit automatiquement en réponse HTTP 400 grâce à l'héritage
`APIException`.
"""
from rest_framework import status
from rest_framework.exceptions import APIException


class BusinessRuleError(APIException):
    """Une règle métier empêche l'opération demandée."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Règle métier non respectée."
    default_code = "business_rule"
