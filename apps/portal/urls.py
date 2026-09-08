"""Routes du portail client — montées sous /api/v1/portal/."""
from django.urls import path

from apps.portal.views import (
    ClientLoginView,
    ClientMeView,
    ClientPortalView,
    ClientRegisterView,
    PortalCatalogView,
    PortalCollecteView,
    PressingListView,
)

app_name = "portal"

urlpatterns = [
    # Comptes clients
    path("pressings/", PressingListView.as_view(), name="pressings"),
    path("register/", ClientRegisterView.as_view(), name="register"),
    path("login/", ClientLoginView.as_view(), name="login"),
    path("me/", ClientMeView.as_view(), name="me"),
    # Catalogue + collectes (X-Portal-Token)
    path("catalog/", PortalCatalogView.as_view(), name="catalog"),
    path("collectes/", PortalCollecteView.as_view(), name="collectes"),
    # Accès rapide par ticket (reçu papier / SMS)
    path("orders/", ClientPortalView.as_view(), name="orders"),
]
