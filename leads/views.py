"""
leads/views.py

Public API views for receiving RFQ form submissions.

Endpoints:
  POST /api/leads/submit/  — accept a form submission
  GET  /api/health/        — health check (returns {"status": "ok"})

The submit view is intentionally kept thin. All business logic lives in
service modules (emails.py) so it can be easily moved to
Celery tasks in the future without changing the view code.

Submit flow (in order):
  1. Honeypot check  — silent 200 if 'website' field is filled
  2. Resolve campaign from api_key
  3. Validate with LeadSerializer
  4. Collect extra / custom fields
  5. Duplicate detection + Lead save + file saves (atomic)
  6. Return 200
"""

import logging
import uuid
from datetime import timedelta

from django.db import transaction

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny

from django.utils.decorators import method_decorator

from campaigns.models import Campaign
from core.utils import get_client_ip
from .models import Lead, RFQFile
from .serializers import LeadSerializer
from .validators import validate_rfq_files


logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Simple health check endpoint.
    Used by uptime monitors, load balancers, and CI pipelines.
    Returns 200 {"status": "ok"} with no authentication required.
    """

    # Public endpoint — no token required
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})




@method_decorator(csrf_exempt, name="dispatch")
class LeadSubmitView(APIView):
    """
    Accept RFQ form submissions from any SMEC landing page.

    Authentication: none — the endpoint is public.
    The api_key in the request body identifies the campaign, not the user.

    Authentication: public endpoint identified by api_key only.
    """

    # Public endpoint — identified by api_key, not by user token
    authentication_classes = []
    permission_classes = [AllowAny]

    # Accept multipart form data (for file uploads) and regular POST forms
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        """
        Handle a single RFQ form submission.
        Executes steps 1-9 in strict order as documented in the module docstring.
        """

        # ------------------------------------------------------------------
        # STEP 1: Honeypot check
        # If the hidden 'website' field has any value, a bot filled it in.
        # Return 200 silently (don't let bots know they were caught).
        # ------------------------------------------------------------------
        if request.data.get("website"):
            logger.info("Honeypot triggered — silent discard")
            return Response({"success": True, "message": "RFQ received."})

        # ------------------------------------------------------------------
        # STEP 2: Resolve campaign from api_key
        # ------------------------------------------------------------------
        api_key = request.data.get("api_key")
        if not api_key:
            return Response(
                {"success": False, "message": "Invalid campaign."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fix 1: Validate UUID format BEFORE hitting the database.
        # On PostgreSQL an invalid UUID string raises DataError — an unhandled 500.
        try:
            uuid.UUID(str(api_key))
        except ValueError:
            return Response(
                {"success": False, "message": "Invalid campaign."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign = Campaign.objects.get(api_key=api_key, is_active=True)
        except Campaign.DoesNotExist:
            logger.warning("Lead submission with invalid api_key: %s", api_key)
            return Response(
                {"success": False, "message": "Invalid campaign."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # STEP 3b: Validate file attachments (before creating the Lead so
        # we don't create a record for an invalid submission)
        # ------------------------------------------------------------------
        files = request.FILES.getlist("rfq_files")
        if files:
            try:
                validate_rfq_files(files)
            except Exception as exc:
                return Response(
                    {"success": False, "errors": {"rfq_files": [str(exc)]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ------------------------------------------------------------------
        # STEP 3: Validate lead data with LeadSerializer
        # Pass the campaign in context so the serializer can apply
        # per-campaign field requirements from fields_config.
        # ------------------------------------------------------------------
        serializer = LeadSerializer(
            data=request.data,
            context={"campaign": campaign},
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # STEP 4: Collect extra / custom fields (Fix 8)
        # Any POST key that is not a declared serializer field, api_key,
        # rfq_files, or website is captured into extra_data. This lets
        # campaigns collect custom fields without model migrations.
        # ------------------------------------------------------------------
        known_fields = set(serializer.fields.keys()) | {"api_key", "rfq_files", "website"}
        extra_data = {
            k: v for k, v in request.data.items() if k not in known_fields
        }

        # ------------------------------------------------------------------
        # STEP 5 + 6 + 7: Duplicate detection, Lead save, and file saves
        #
        # Fix 4: Duplicate check and lead save share one atomic block so two
        #         simultaneous requests cannot both read exists()=False and
        #         both save as non-duplicates (race condition).
        #
        # Fix 3: Lead save and all RFQFile saves share the same atomic block
        #         so a mid-loop file failure rolls back the Lead as well —
        #         no partial records left in the database.
        #
        # Fix 2: The entire block is wrapped in try/except so any DB error
        #         (DB down, constraint violation, disk full) returns a clean
        #         500 JSON response instead of an unhandled exception traceback.
        # ------------------------------------------------------------------
        email = serializer.validated_data.get("email", "")
        cutoff = timezone.now() - timedelta(hours=24)

        try:
            with transaction.atomic():
                # Duplicate detection — inside the transaction so the check
                # and the subsequent save are seen as one operation.
                is_duplicate = Lead.objects.filter(
                    email=email,
                    campaign=campaign,
                    submitted_at__gte=cutoff,
                ).exists()

                if is_duplicate:
                    logger.info(
                        "Duplicate lead detected: email=%s campaign=%s",
                        email,
                        campaign.slug,
                    )

                # Save Lead — inside the transaction so a subsequent file
                # save failure rolls back this record too.
                lead = serializer.save(
                    campaign=campaign,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    referrer=request.META.get("HTTP_REFERER", ""),
                    is_duplicate=is_duplicate,
                    extra_data=extra_data,
                )

                logger.info(
                    "Lead saved: id=%s campaign=%s email=%s duplicate=%s",
                    lead.id,
                    campaign.slug,
                    lead.email,
                    is_duplicate,
                )

                # Save file attachments — inside the transaction so any failure
                # here rolls back the Lead record as well.
                for f in files:
                    RFQFile.objects.create(
                        lead=lead,
                        file=f,
                        original_name=f.name,
                        file_size=f.size,
                    )

        except Exception as exc:
            logger.error("Lead save failed: %s", exc, exc_info=True)
            return Response(
                {"success": False, "message": "Submission failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ------------------------------------------------------------------
        # STEP 7: Return success
        # ------------------------------------------------------------------
        return Response({"success": True, "message": "RFQ received."})
