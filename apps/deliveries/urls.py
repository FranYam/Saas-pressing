"""Routes deliveries — montées sous /api/v1/deliveries/."""
from rest_framework.routers import DefaultRouter

from apps.deliveries.views import CourierViewSet

app_name = "deliveries"

router = DefaultRouter()
router.register("couriers", CourierViewSet, basename="couriers")

urlpatterns = router.urls
