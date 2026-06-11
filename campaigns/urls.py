"""
campaigns/urls.py

URL patterns for the campaigns app.

All routes are mounted under /api/ by the root smec/urls.py, giving:
  GET  /api/campaigns/       — list all campaigns with lead counts (token auth)
  POST /api/campaigns/       — create a new campaign (token auth)
  PUT  /api/campaigns/<id>/  — update a campaign (token auth)
"""

from django.urls import path
from .panel_views import CampaignListCreateView, CampaignUpdateView

app_name = "campaigns"

urlpatterns = [
    # Campaign list and create share the same URL, differentiated by HTTP method
    path("campaigns/", CampaignListCreateView.as_view(), name="campaign-list-create"),

    # Campaign update (PUT only — slug and api_key are immutable)
    path("campaigns/<int:pk>/", CampaignUpdateView.as_view(), name="campaign-update"),
]
