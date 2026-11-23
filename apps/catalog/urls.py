"""Routes catalogue — montées sous /api/catalog/."""
from rest_framework.routers import DefaultRouter

from apps.catalog.views import TarifViewSet

app_name = "catalog"

router = DefaultRouter()
router.register("", TarifViewSet, basename="tarifs")

urlpatterns = router.urls
