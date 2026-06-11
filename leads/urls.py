"""
leads/urls.py

URL patterns for the leads app.

All routes are mounted under /api/ by the root smec/urls.py, giving:
  POST /api/leads/submit/        — RFQ form submission (public)
  GET  /api/health/              — health check (public)
  GET  /api/dashboard/stats/    — sales dashboard aggregate stats (token auth)
  GET  /api/leads/               — paginated lead list with filters (token auth)
  GET  /api/leads/<id>/          — single lead detail (token auth)
  PATCH /api/leads/<id>/         — update lead status/notes (token auth)
"""

from django.urls import path
from .views import LeadSubmitView, HealthCheckView
from .dashboard_views import DashboardStatsView
from .panel_views import LeadListView, LeadDetailUpdateView

app_name = "leads"

urlpatterns = [
    # ------------------------------------------------------------------
    # Public endpoints — no token required (views override AllowAny)
    # ------------------------------------------------------------------
    path("leads/submit/", LeadSubmitView.as_view(), name="lead-submit"),
    path("health/", HealthCheckView.as_view(), name="health-check"),

    # ------------------------------------------------------------------
    # Dashboard stats — requires token authentication
    # ------------------------------------------------------------------
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),

    # ------------------------------------------------------------------
    # Lead panel — requires token authentication
    # ------------------------------------------------------------------
    path("leads/", LeadListView.as_view(), name="lead-list"),
    path("leads/<int:pk>/", LeadDetailUpdateView.as_view(), name="lead-detail"),
]
