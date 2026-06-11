"""
campaigns/admin.py

Admin configuration for Campaign management.

Sales/marketing staff can create campaigns, view their api_keys,
and track how many leads each campaign has generated.
"""

from django.contrib import admin
from django.db.models import Count

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin view for the Campaign model."""

    # Columns shown in the list view
    list_display = ("name", "slug", "is_active", "lead_count", "created_at", "notify_email")

    # Sidebar filters
    list_filter = ("is_active", "created_at")

    # Full-text search
    search_fields = ("name", "slug", "url")

    # Auto-generate slug from name while typing (JS helper in admin)
    prepopulated_fields = {"slug": ("name",)}

    # These fields are system-generated and must not be edited
    readonly_fields = ("api_key", "created_at")

    # Organise the detail form into logical sections
    fieldsets = (
        (
            "Campaign Identity",
            {
                "fields": ("name", "slug", "api_key", "url", "description", "is_active"),
            },
        ),
        (
            "Notifications & Integrations",
            {
                "fields": ("notify_email", "sheets_id"),
                "description": (
                    "notify_email overrides the global SALES_EMAIL for this campaign. "
                    "sheets_id is the Google Spreadsheet ID from the sheet URL."
                ),
            },
        ),
        (
            "Field Configuration",
            {
                "fields": ("fields_config",),
                "description": (
                    'JSON object controlling which fields are "required", "optional", or "hidden" '
                    "for this campaign's form. Example: "
                    '{"company": "required", "phone": "required", "industry": "required"}'
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
            },
        ),
    )

    # Bulk actions
    actions = ["activate_selected", "deactivate_selected"]

    # -----------------------------------------------------------------------
    # Queryset — annotate with lead count to avoid N+1 queries
    # -----------------------------------------------------------------------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_lead_count=Count("leads"))

    # -----------------------------------------------------------------------
    # Custom list_display column: lead count
    # -----------------------------------------------------------------------
    @admin.display(description="Leads", ordering="_lead_count")
    def lead_count(self, obj):
        return obj._lead_count

    # -----------------------------------------------------------------------
    # Bulk actions
    # -----------------------------------------------------------------------
    @admin.action(description="Activate selected campaigns")
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} campaign(s) activated.")

    @admin.action(description="Deactivate selected campaigns")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} campaign(s) deactivated.")
