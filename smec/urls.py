"""
smec/urls.py

Root URL configuration for the SMEC Backend project.

All API routes are namespaced under /api/ and split across app-level url files:
  - /api/auth/       → core app  (token login)
  - /api/leads/      → leads app (submit, health, dashboard, panel)
  - /api/campaigns/  → campaigns app (panel)

In development, Django also serves media files (uploaded RFQ attachments)
directly. In production these are served by S3/R2.
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from core.auth_views import LoginView

urlpatterns = [
    # Django admin panel for the sales team
    path("admin/", admin.site.urls),

    # Token authentication — public endpoint, no token required
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),

    # Lead endpoints: submit (public), health (public), dashboard + panel (token auth)
    path("api/", include("leads.urls")),

    # Campaign panel endpoints (token auth)
    path("api/", include("campaigns.urls")),
]

# Serve uploaded files locally during development
# In production, files are served directly from S3/R2
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
