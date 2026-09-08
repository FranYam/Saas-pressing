"""Routes du portail client — montées sous /api/v1/portal/."""
from django.urls import path

from apps.portal.views import ClientPortalView

app_name = "portal"

urlpatterns = [
    path("orders/", ClientPortalView.as_view(), name="orders"),
]
