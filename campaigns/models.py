"""
campaigns/models.py

Defines the Campaign model — one record per SMEC landing page.

Each campaign has a unique api_key (UUID) which is embedded in the
static HTML form. When a form is submitted, the view uses this api_key
to identify which campaign the lead belongs to.

The fields_config JSONField lets you control which optional lead fields
are required, optional, or hidden on a per-campaign basis — without
ever touching the Lead model or running migrations.

Example fields_config:
{
    "company": "required",
    "phone": "required",
    "country": "optional",
    "industry": "required",
    "requirement_type": "optional",
    "file_upload": "optional"
}
"""

import uuid
from django.db import models


class Campaign(models.Model):
    """
    Represents one landing page / lead generation campaign.

    Each static HTML page should have exactly one Campaign record
    and must send its api_key with every form submission.
    """

    name = models.CharField(
        max_length=200,
        help_text="Human-readable campaign name, e.g. 'Oil & Gas Landing Page'",
    )
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly identifier, e.g. 'oil-gas-landing'",
    )
    api_key = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Auto-generated UUID. Embed this in the static HTML form as SMEC_CONFIG.apiKey.",
    )
    url = models.URLField(
        blank=True,
        help_text="Public URL of the landing page (for reference only)",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal notes about this campaign",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive campaigns reject form submissions with a 400 error",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Where to send sales notification emails for this campaign.
    # Falls back to settings.SALES_EMAIL if left blank.
    notify_email = models.EmailField(
        blank=True,
        help_text="Sales notification email for this campaign. Falls back to SALES_EMAIL setting if blank.",
    )

    # Google Sheets spreadsheet ID where leads from this campaign are logged.
    # Leave blank to disable Sheets integration for this campaign.
    sheets_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Google Sheets spreadsheet ID (from the sheet URL). Leave blank to skip.",
    )

    # Per-campaign field configuration — drives dynamic validation.
    # Keys are Lead field names; values are "required", "optional", or "hidden".
    fields_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Controls which optional fields are required/optional/hidden for this campaign. '
            'Example: {"company": "required", "phone": "required", "country": "optional", '
            '"industry": "required", "requirement_type": "optional", "file_upload": "optional"}'
        ),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"

    def __str__(self):
        return self.name
