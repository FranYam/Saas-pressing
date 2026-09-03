"""Routes accounts — authentification JWT (socle, Issue #4).

Login avec le numéro de téléphone (username) + mot de passe.
La gestion des employés (/api/v1/accounts/employees/) arrive à l'Issue #4.
"""
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("login/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("login/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
