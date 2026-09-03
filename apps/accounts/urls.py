"""Routes accounts — authentification JWT, profil courant, gestion de l'équipe."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts.views import EmployeeViewSet, LoginView, MeView

app_name = "accounts"

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employees")

urlpatterns = [
    path("login/", LoginView.as_view(), name="token_obtain_pair"),
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("login/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
