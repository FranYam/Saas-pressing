"""Routes payments_gateway — montées sous /api/v1/payments-gateway/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments_gateway.views import (
    InitiateMobileMoneyView,
    MobileMoneyRequestViewSet,
)
from apps.payments_gateway.webhooks import OperatorWebhookView

app_name = "payments_gateway"

router = DefaultRouter()
router.register("requests", MobileMoneyRequestViewSet, basename="requests")

urlpatterns = [
    path("initiate/", InitiateMobileMoneyView.as_view(), name="initiate"),
    path("webhook/<str:operator>/", OperatorWebhookView.as_view(), name="webhook"),
    path("", include(router.urls)),
]
