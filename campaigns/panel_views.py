"""
campaigns/panel_views.py

Sales dashboard panel views for managing campaigns.

Endpoints:
  GET  /api/campaigns/       — list all campaigns (with lead counts)
  POST /api/campaigns/       — create a new campaign
  PUT  /api/campaigns/{id}/  — update an existing campaign

Authentication: TokenAuthentication + IsAuthenticated (global DRF defaults).

Notes:
  - api_key is auto-generated on creation and is never writable.
  - slug is set on creation and is ignored on PUT (slugs are immutable).
  - fields_config is validated to be a JSON object (dict), not a list.
"""

import logging

from django.db.models import Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Campaign
from .serializers import CampaignSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared queryset helper
# ---------------------------------------------------------------------------

def _campaign_queryset():
    """
    Base queryset used by both list and detail views.

    annotate(lead_count=...) adds a `lead_count` attribute to each Campaign
    instance so CampaignSerializer.lead_count can read it without a subquery.
    """
    return (
        Campaign.objects
        .annotate(lead_count=Count("leads"))
        .order_by("name")
    )


# ---------------------------------------------------------------------------
# Campaign List + Create
# ---------------------------------------------------------------------------

class CampaignListCreateView(APIView):
    """
    GET  /api/campaigns/  — return all campaigns with lead counts
    POST /api/campaigns/  — create a new campaign

    No pagination — campaign count is expected to stay small (tens, not thousands).
    """

    def get(self, request):
        """Return all campaigns ordered by name, each with an annotated lead count."""
        try:
            campaigns = _campaign_queryset()
            serializer = CampaignSerializer(campaigns, many=True, context={"request": request})
            return Response(serializer.data)

        except Exception as exc:
            logger.error("CampaignListCreateView.get error: %s", exc, exc_info=True)
            return Response(
                {"error": "Unable to fetch campaigns."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """
        Create a new campaign.

        Required fields : name, slug
        Optional fields : url, description, notify_email, is_active,
                          fields_config
        Auto-generated  : api_key (UUID), created_at

        Returns 400 { "error": "Slug already exists" } on duplicate slug.
        Returns 400 with serializer errors for other validation failures.
        Returns 201 with the created campaign object on success.
        """
        try:
            # Duplicate slug check before hitting the serializer so we return
            # a consistent error shape instead of a DRF unique-constraint error
            slug = request.data.get("slug", "").strip()
            if slug and Campaign.objects.filter(slug=slug).exists():
                return Response(
                    {"error": "Slug already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate fields_config must be a JSON object (dict), not a list
            fields_config = request.data.get("fields_config")
            if fields_config is not None and not isinstance(fields_config, dict):
                return Response(
                    {"error": "fields_config must be a JSON object, not a list or primitive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = CampaignSerializer(data=request.data, context={"request": request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            campaign = serializer.save()

            # Re-fetch with lead_count annotation so the response is consistent
            # with what the list endpoint returns
            campaign = _campaign_queryset().get(pk=campaign.pk)
            response_serializer = CampaignSerializer(campaign, context={"request": request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.error("CampaignListCreateView.post error: %s", exc, exc_info=True)
            return Response(
                {"error": "Unable to create campaign."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Campaign Update
# ---------------------------------------------------------------------------

class CampaignUpdateView(APIView):
    """
    PUT /api/campaigns/{id}/

    Update an existing campaign. Slug and api_key are immutable — if the
    client sends either field it is silently ignored. All other writable
    fields are accepted.

    Returns 404 if the campaign does not exist.
    Returns the updated campaign object on success.
    """

    def _get_campaign_or_404(self, pk):
        """Fetch a campaign by PK with lead count annotated, or return None."""
        try:
            return _campaign_queryset().get(pk=pk)
        except Campaign.DoesNotExist:
            return None

    def put(self, request, pk):
        """Perform a full update, silently dropping slug and api_key if sent."""
        try:
            campaign = self._get_campaign_or_404(pk)
            if campaign is None:
                return Response(
                    {"error": "Campaign not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Strip slug from the incoming data so it cannot be changed
            # (make a mutable copy of QueryDict / dict)
            data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
            data.pop("slug", None)    # slug is immutable after creation
            data.pop("api_key", None) # api_key is always system-managed

            # Validate fields_config must be a JSON object if provided
            fields_config = data.get("fields_config")
            if fields_config is not None and not isinstance(fields_config, dict):
                return Response(
                    {"error": "fields_config must be a JSON object, not a list or primitive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # partial=False (PUT semantics), but slug/api_key already removed
            serializer = CampaignSerializer(
                campaign,
                data=data,
                partial=True,         # allows omitting slug since we stripped it
                context={"request": request},
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()

            # Re-fetch to get a fresh lead_count annotation
            campaign = self._get_campaign_or_404(pk)
            response_serializer = CampaignSerializer(campaign, context={"request": request})
            return Response(response_serializer.data)

        except Exception as exc:
            logger.error("CampaignUpdateView.put error pk=%s: %s", pk, exc, exc_info=True)
            return Response(
                {"error": "Unable to update campaign."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
