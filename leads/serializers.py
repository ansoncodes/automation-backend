"""
leads/serializers.py

LeadSerializer — validates RFQ form submissions.

The serializer is campaign-aware: it reads the campaign's fields_config
at instantiation time and dynamically adjusts which fields are required,
optional, or excluded from validation. This means:

  - Adding a new required field to a campaign is a config change in the
    admin panel, not a code change.
  - No migrations are ever needed to change per-campaign field requirements.

Usage:
    serializer = LeadSerializer(
        data=request.data,
        context={"campaign": campaign}
    )
"""

import re
from rest_framework import serializers

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    """
    Serializer for the Lead model.

    Validation is campaign-aware — field requirements are adjusted
    dynamically based on the campaign's fields_config JSON.
    """

    class Meta:
        model = Lead
        fields = [
            "full_name",
            "email",
            "message",
            "consent",
            "company",
            "phone",
            "country",
            "industry",
            "requirement_type",
            "form_location",
            "extra_data",
        ]
        extra_kwargs = {
            # Optional fields are blank=True in the model;
            # make them non-required by default here.
            # The __init__ below will override based on fields_config.
            "company": {"required": False},
            "phone": {"required": False},
            "country": {"required": False},
            "industry": {"required": False},
            "requirement_type": {"required": False},
            "form_location": {"required": False},
            "extra_data": {"required": False},
        }

    def __init__(self, *args, **kwargs):
        """
        Dynamically adjust field requirements based on the campaign's
        fields_config at serializer instantiation time.

        This runs before any validation so validation reflects the
        campaign-specific rules.
        """
        super().__init__(*args, **kwargs)

        # Retrieve campaign from context (passed in by the view)
        campaign = self.context.get("campaign")
        if not campaign:
            return

        fields_config = campaign.fields_config or {}

        # Fields that can be controlled by fields_config
        configurable_fields = [
            "company",
            "phone",
            "country",
            "industry",
            "requirement_type",
        ]

        for field_name in configurable_fields:
            config_value = fields_config.get(field_name)

            if config_value == "required":
                if field_name in self.fields:
                    self.fields[field_name].required = True

            elif config_value == "optional":
                if field_name in self.fields:
                    self.fields[field_name].required = False

            elif config_value == "hidden":
                # Remove the field entirely — it won't appear in validated_data
                self.fields.pop(field_name, None)

            # If not mentioned in fields_config, leave as default (optional)

    # -----------------------------------------------------------------------
    # Field-level validators
    # -----------------------------------------------------------------------

    def validate_full_name(self, value):
        """
        Strip whitespace and reject empty or whitespace-only names.
        """
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate_consent(self, value):
        """
        Consent must be explicitly True.
        The form sends "true" as a string; DRF BooleanField coerces it.
        """
        if not value:
            raise serializers.ValidationError(
                "You must consent to be contacted in order to submit this form."
            )
        return value

    def validate_email(self, value):
        """
        Standard email format validation (DRF EmailField handles most of this,
        but we normalise to lowercase to make duplicate detection consistent).
        """
        return value.strip().lower()

    def validate_phone(self, value):
        """
        Strip all non-digit characters and validate length.
        Blank phone is allowed (field may be optional per campaign config).
        """
        if not value:
            return value

        digits_only = re.sub(r"\D", "", value)

        if len(digits_only) < 7:
            raise serializers.ValidationError(
                "Phone number is too short. Please enter at least 7 digits."
            )
        if len(digits_only) > 15:
            raise serializers.ValidationError(
                "Phone number is too long. Please enter at most 15 digits."
            )

        return value  # return original value (with formatting chars)

    def validate_message(self, value):
        """
        Message must have at least 10 characters to filter out empty or
        trivially short submissions.
        """
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Please describe your requirement in at least 10 characters."
            )
        return value.strip()


# ---------------------------------------------------------------------------
# Panel / dashboard serializers — used by the sales dashboard API only.
# These are read-only representations; they never touch the submit flow.
# ---------------------------------------------------------------------------

from .models import RFQFile  # noqa: E402 — placed here to avoid a circular import


class RFQFileSerializer(serializers.ModelSerializer):
    """
    Serializer for RFQFile instances.

    Adds a `url` field that returns the fully-qualified download link so the
    dashboard frontend can render a clickable link without knowing the storage
    backend (local vs. S3).
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = RFQFile
        fields = ["id", "original_name", "file_size", "uploaded_at", "url"]

    def get_url(self, obj):
        """Build an absolute URI for the stored file using the current request."""
        request = self.context.get("request")
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        # Fall back to a relative URL if no request is in context
        return obj.file.url if obj.file else None


class LeadListSerializer(serializers.ModelSerializer):
    """
    Full read-only representation of a Lead for the list and detail endpoints.

    Includes:
      - All Lead model fields
      - campaign_name  — resolved from the FK (avoids a second query with select_related)
      - files          — nested list of attached RFQ files with download URLs
    """

    # Resolve campaign name directly from the FK so the frontend never needs
    # to make a second call to /api/campaigns/{id}/
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    # Nested file list — read-only; files are created by the submit view
    files = RFQFileSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "campaign",
            "campaign_name",
            "full_name",
            "email",
            "company",
            "phone",
            "country",
            "industry",
            "requirement_type",
            "message",
            "form_location",
            "referrer",
            "ip_address",
            "user_agent",
            "submitted_at",
            "status",
            "is_duplicate",
            "sheets_synced",
            "notes",
            "extra_data",
            "consent",
            "files",
        ]


class LeadUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer for PATCH /api/leads/{id}/.

    Only `status` and `notes` are accepted — all other fields are silently
    ignored. Status is validated against the Lead model's STATUS_CHOICES.
    """

    # Derive valid choices directly from the model so this never drifts
    VALID_STATUSES = [choice[0] for choice in Lead.STATUS_CHOICES]

    class Meta:
        model = Lead
        fields = ["status", "notes"]

    def validate_status(self, value):
        """Reject any status value not defined in Lead.STATUS_CHOICES."""
        if value not in self.VALID_STATUSES:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(self.VALID_STATUSES)}."
            )
        return value
