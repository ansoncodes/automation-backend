"""
campaigns/serializers.py

CampaignSerializer — read/write representation of a Campaign for the
sales dashboard panel endpoints.

Used by:
  GET  /api/campaigns/       — list all campaigns with lead counts
  POST /api/campaigns/       — create a new campaign
  PUT  /api/campaigns/{id}/  — update an existing campaign
"""

from rest_framework import serializers

from .models import Campaign


class CampaignSerializer(serializers.ModelSerializer):
    """
    Full serializer for the Campaign model.

    Fields that are always read-only:
      - api_key    — auto-generated UUID; never accepted from clients
      - created_at — set on creation; immutable thereafter
      - lead_count — annotated by the view queryset; not a model field

    The `fields_config` field accepts any JSON object. The view validates
    that the submitted value is a dict (not a list or primitive).
    """

    # Annotated by the queryset in CampaignListCreateView; read-only here
    lead_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "slug",
            "api_key",
            "url",
            "description",
            "is_active",
            "created_at",
            "notify_email",
            "fields_config",
            "lead_count",
        ]
        # api_key and created_at are system-managed — never writable via API
        read_only_fields = ["api_key", "created_at"]
