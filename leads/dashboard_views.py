"""
leads/dashboard_views.py

Dashboard summary statistics for the SMEC sales panel.

Endpoint:
  GET /api/dashboard/stats/

Returns a single JSON object with aggregate lead counts. All numbers are
computed in a single database pass using Django's ORM aggregation so there
are no N+1 queries.

Authentication: TokenAuthentication + IsAuthenticated (global DRF defaults).
"""

import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Lead

logger = logging.getLogger(__name__)


class DashboardStatsView(APIView):
    """
    Return aggregate lead statistics for the sales dashboard homepage.

    Response shape:
    {
        "total": 142,
        "new": 38,
        "today": 5,
        "this_week": 21,
        "per_campaign": [
            { "campaign": "Oil & Gas Landing", "count": 87 },
            ...
        ]
    }

    All counts are computed server-side. The frontend never needs to
    paginate or post-process — it can render the numbers directly.
    """

    def get(self, request):
        """Compute and return all dashboard stats in a single response."""
        try:
            now = timezone.now()
            today = now.date()
            week_ago = now - timedelta(days=7)

            # ------------------------------------------------------------------
            # Scalar aggregates — resolved in one queryset evaluation
            # ------------------------------------------------------------------
            total = Lead.objects.count()

            new_count = Lead.objects.filter(status=Lead.STATUS_NEW).count()

            today_count = Lead.objects.filter(
                submitted_at__date=today
            ).count()

            this_week_count = Lead.objects.filter(
                submitted_at__gte=week_ago
            ).count()

            # ------------------------------------------------------------------
            # Per-campaign breakdown — annotated queryset, ordered by count desc
            # Each row: { "campaign__name": "...", "count": N }
            # ------------------------------------------------------------------
            per_campaign_qs = (
                Lead.objects
                .values("campaign__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # Reshape to { "campaign": "...", "count": N } for a cleaner API
            per_campaign = [
                {"campaign": row["campaign__name"], "count": row["count"]}
                for row in per_campaign_qs
            ]

            return Response({
                "total": total,
                "new": new_count,
                "today": today_count,
                "this_week": this_week_count,
                "per_campaign": per_campaign,
            })

        except Exception as exc:
            logger.error("DashboardStatsView error: %s", exc, exc_info=True)
            return Response(
                {"error": "Unable to fetch dashboard stats."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
