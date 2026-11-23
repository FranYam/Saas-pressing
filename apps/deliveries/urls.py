"""Routes deliveries — montées sous /api/deliveries/."""
from rest_framework.routers import DefaultRouter

from apps.deliveries.views import CourierViewSet

app_name = "deliveries"

router = DefaultRouter()
router.register("couriers", CourierViewSet, basename="couriers")

urlpatterns = router.urls
