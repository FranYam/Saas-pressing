"""Routes clients — montées sous /api/v1/clients/."""
from rest_framework.routers import DefaultRouter

from apps.clients.views import ClientViewSet

app_name = "clients"

router = DefaultRouter()
router.register("", ClientViewSet, basename="clients")

urlpatterns = router.urls
