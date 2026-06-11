"""
core/dashboard_view.py

Simple view to serve the sales dashboard HTML template.
This renders templates/dashboard.html at the root URL.
"""

from django.shortcuts import render
from django.views import View


class DashboardView(View):
    """Render the sales dashboard SPA."""

    def get(self, request):
        return render(request, "dashboard.html")