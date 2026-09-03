"""Pagination standard de l'API (clients mobiles, connexions lentes)."""
from rest_framework import pagination


class StandardResultsSetPagination(pagination.PageNumberPagination):
    """Pagination par page avec taille paramétrable et plafonnée."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
