"""Isolation multi-tenant au niveau des querysets (Issue #2).

Règle centrale du projet : deux pressings distincts ne voient jamais les
données l'un de l'autre. Tout ViewSet métier DOIT hériter de
`TenantScopedQuerysetMixin` pour que le filtrage soit appliqué partout,
de la même façon, sans duplication dans chaque vue.
"""
from django.db.models import QuerySet


class TenantScopedQuerysetMixin:
    """
    Filtre automatiquement le queryset de la vue sur le pressing de
    l'utilisateur connecté (`request.user.pressing`).

    - Un super-utilisateur plateforme (sans pressing) voit tout.
    - Un utilisateur authentifié sans pressing voit un queryset vide :
      comportement « fail-closed », on ne renvoie jamais tout par défaut.
    """

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        pressing_id = getattr(user, "pressing_id", None)
        if pressing_id is None:
            return queryset.none()

        return queryset.filter(pressing_id=pressing_id)
