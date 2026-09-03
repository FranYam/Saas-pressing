"""Routes tenants — inscription publique et profil (theming PWA)."""
from django.urls import path

from apps.tenants.views import PressingProfileView, PressingRegisterView

app_name = "tenants"

urlpatterns = [
    path("register/", PressingRegisterView.as_view(), name="register"),
    path("profile/", PressingProfileView.as_view(), name="profile"),
]
