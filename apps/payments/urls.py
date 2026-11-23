"""Routes payments — montées sous /api/payments/."""
from rest_framework.routers import DefaultRouter

from apps.payments.views import PaiementViewSet

app_name = "payments"

router = DefaultRouter()
router.register("", PaiementViewSet, basename="paiements")

urlpatterns = router.urls
