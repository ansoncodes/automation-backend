"""
leads/panel_views.py

Sales dashboard panel views for browsing and updating leads.

Endpoints:
  GET   /api/leads/          — paginated, filterable lead list
  GET   /api/leads/{id}/     — single lead detail
  PATCH /api/leads/{id}/     — update status and/or notes only

Authentication: TokenAuthentication + IsAuthenticated (global DRF defaults).
Do not import or modify LeadSubmitView — that lives in leads/views.py.
"""

import logging

from django.utils import timezone
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from .models import Lead
from .serializers import LeadListSerializer, LeadUpdateSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class LeadPagination(PageNumberPagination):
    """25 leads per page; page number supplied via ?page= query param."""
    page_size = 25
    page_size_query_param = "page_size"   # allow override in tests if needed
    max_page_size = 100


# ---------------------------------------------------------------------------
# Helper — shared queryset builder
# ---------------------------------------------------------------------------

def _build_lead_queryset(params):
    """
    Return a filtered, ordered Lead queryset based on the provided query
    parameters dict (usually request.query_params).

    Supported filters:
      search        — full_name, email, or company (case-insensitive contains)
      campaign      — campaign FK id (exact)
      status        — Lead.status (exact)
      industry      — Lead.industry (exact)
      form_location — Lead.form_location (exact)
      date_from     — submitted_at__date >= value
      date_to       — submitted_at__date <= value
    """
    # select_related avoids a second query for campaign.name on every lead
    # prefetch_related avoids N+1 queries when serialising files
    qs = (
        Lead.objects
        .select_related("campaign")
        .prefetch_related("files")
        .order_by("-submitted_at")
    )

    # Full-text search across name, email, company
    search = params.get("search", "").strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(email__icontains=search)
            | Q(company__icontains=search)
        )

    # Exact-match filters
    campaign_id = params.get("campaign", "").strip()
    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)

    lead_status = params.get("status", "").strip()
    if lead_status:
        qs = qs.filter(status=lead_status)

    industry = params.get("industry", "").strip()
    if industry:
        qs = qs.filter(industry=industry)

    form_location = params.get("form_location", "").strip()
    if form_location:
        qs = qs.filter(form_location=form_location)

    # Date-range filters on submitted_at (date part only)
    date_from = params.get("date_from", "").strip()
    if date_from:
        qs = qs.filter(submitted_at__date__gte=date_from)

    date_to = params.get("date_to", "").strip()
    if date_to:
        qs = qs.filter(submitted_at__date__lte=date_to)

    return qs


# ---------------------------------------------------------------------------
# Lead List
# ---------------------------------------------------------------------------

class LeadListView(APIView):
    """
    GET /api/leads/

    Returns a paginated, filterable list of leads ordered newest-first.
    See _build_lead_queryset() for supported query parameters.

    Response shape mirrors DRF's PageNumberPagination:
    {
        "count": 142,
        "next": "/api/leads/?page=2",
        "previous": null,
        "results": [ ...leads... ]
    }
    """

    def get(self, request):
        """Filter, paginate, and serialise leads."""
        try:
            qs = _build_lead_queryset(request.query_params)

            paginator = LeadPagination()
            page = paginator.paginate_queryset(qs, request, view=self)

            serializer = LeadListSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return paginator.get_paginated_response(serializer.data)

        except Exception as exc:
            logger.error("LeadListView error: %s", exc, exc_info=True)
            return Response(
                {"error": "Unable to fetch leads."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Lead Detail + Update
# ---------------------------------------------------------------------------

class LeadDetailUpdateView(APIView):
    """
    GET   /api/leads/{id}/   — full lead detail
    PATCH /api/leads/{id}/   — update status and/or notes only

    Only `status` and `notes` are writable via PATCH. All other fields are
    read-only and any extra keys sent by the client are silently ignored by
    LeadUpdateSerializer.
    """

    def _get_lead_or_404(self, pk):
        """
        Fetch a lead with its campaign and files pre-fetched.
        Returns the Lead instance, or None if not found.
        """
        try:
            return (
                Lead.objects
                .select_related("campaign")
                .prefetch_related("files")
                .get(pk=pk)
            )
        except Lead.DoesNotExist:
            return None

    def get(self, request, pk):
        """Return the full lead detail object."""
        try:
            lead = self._get_lead_or_404(pk)
            if lead is None:
                return Response(
                    {"error": "Lead not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = LeadListSerializer(lead, context={"request": request})
            return Response(serializer.data)

        except Exception as exc:
            logger.error("LeadDetailUpdateView.get error pk=%s: %s", pk, exc, exc_info=True)
            return Response(
                {"error": "Unable to fetch lead."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        """
        Partially update a lead's status and/or notes.

        Only fields declared in LeadUpdateSerializer (status, notes) are
        accepted. Status must be one of the Lead.STATUS_CHOICES values.
        Returns the full updated lead object on success.
        """
        try:
            lead = self._get_lead_or_404(pk)
            if lead is None:
                return Response(
                    {"error": "Lead not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # partial=True so the client can send just status or just notes
            serializer = LeadUpdateSerializer(lead, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()

            # Return the full representation after the update
            response_serializer = LeadListSerializer(
                lead,
                context={"request": request},
            )
            return Response(response_serializer.data)

        except Exception as exc:
            logger.error("LeadDetailUpdateView.patch error pk=%s: %s", pk, exc, exc_info=True)
            return Response(
                {"error": "Unable to update lead."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
