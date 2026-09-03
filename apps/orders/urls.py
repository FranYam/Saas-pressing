"""Routes orders — montées sous /api/v1/orders/."""
from rest_framework.routers import DefaultRouter

from apps.orders.views import CommandeViewSet

app_name = "orders"

router = DefaultRouter()
router.register("", CommandeViewSet, basename="commandes")

urlpatterns = router.urls
