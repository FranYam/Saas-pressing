"""Routes principales de l'API.

Chaque app métier porte son propre `urls.py`, monté ici sous /api/v1/<app>/.
Documentation OpenAPI servie par drf-spectacular (Issue #1).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

api_v1 = [
    path("accounts/", include("apps.accounts.urls")),
    path("tenants/", include("apps.tenants.urls")),
    path("clients/", include("apps.clients.urls")),
    path("orders/", include("apps.orders.urls")),
    path("payments/", include("apps.payments.urls")),
    path("payments-gateway/", include("apps.payments_gateway.urls")),
    path("deliveries/", include("apps.deliveries.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # La vue de schéma est publique (le défaut IsAuthenticated la bloquerait).
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/v1/", include(api_v1)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns.insert(0, path("__debug__/", include("debug_toolbar.urls")))
