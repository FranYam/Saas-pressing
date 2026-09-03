"""Routes dashboard — montées sous /api/v1/dashboard/."""
from django.urls import path

from apps.dashboard.views import DashboardSummaryView

app_name = "dashboard"

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="summary"),
]
