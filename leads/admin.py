"""
leads/admin.py

Admin configuration for Lead and RFQFile management.

The sales team uses this panel to:
  - View all incoming RFQ leads in a filterable, searchable list
  - Update lead status (reviewed, contacted, quoted, closed, spam)
  - Add internal notes
  - View attached files inline
  - Export filtered leads to CSV
  - Resend sales notification emails
  - Retry failed Google Sheets syncs
  - Bulk-mark leads by status

All system-generated fields (IP, timestamp, flags) are readonly to
prevent accidental modification.
"""

import csv
import logging

from django.contrib import admin
from django.http import StreamingHttpResponse
from django.conf import settings

from .models import Lead, RFQFile
from .sheets import push_to_sheets

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CSV streaming helper
# ---------------------------------------------------------------------------
class EchoBuffer:
    """A minimal object that implements the write interface for csv.writer."""
    def write(self, value):
        return value


# ---------------------------------------------------------------------------
# RFQFile inline — shown inside the Lead detail page
# ---------------------------------------------------------------------------
class RFQFileInline(admin.TabularInline):
    """Display uploaded files as a read-only table inside the Lead form."""

    model = RFQFile
    extra = 0  # don't show empty add-new rows
    readonly_fields = ("original_name", "file", "file_size", "uploaded_at")
    can_delete = False  # prevent accidental deletion from admin

    def has_add_permission(self, request, obj=None):
        """Files are uploaded by the form only — never added via admin."""
        return False


# ---------------------------------------------------------------------------
# Lead admin
# ---------------------------------------------------------------------------
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """
    Full-featured admin for the Lead model.

    Key features:
      - Rich list view with all tracking flags visible at a glance
      - Sidebar filters for every useful dimension
      - Full-text search across contact fields
      - Inline file attachments (read-only)
      - Bulk status updates
      - CSV export with streaming (no memory limit for large exports)
      - Resend email / retry Sheets sync actions
    """

    # -----------------------------------------------------------------------
    # List view configuration
    # -----------------------------------------------------------------------
    list_display = (
        "submitted_at",
        "full_name",
        "company",
        "email",
        "campaign",
        "industry",
        "status",
        "form_location",
        "is_duplicate",
        "sheets_synced",
    )

    list_filter = (
        "campaign",
        "status",
        "industry",
        "form_location",
        "is_duplicate",
        "submitted_at",
        "sheets_synced",
    )

    search_fields = ("full_name", "company", "email", "phone")

    date_hierarchy = "submitted_at"

    list_per_page = 50

    ordering = ("-submitted_at",)

    # -----------------------------------------------------------------------
    # Detail view configuration
    # -----------------------------------------------------------------------
    readonly_fields = (
        "campaign",
        "ip_address",
        "user_agent",
        "referrer",
        "submitted_at",
        "is_duplicate",
        "sheets_synced",
    )

    inlines = [RFQFileInline]

    fieldsets = (
        (
            "Lead Information",
            {
                "fields": (
                    "campaign",
                    "full_name",
                    "email",
                    "company",
                    "phone",
                    "country",
                    "industry",
                    "requirement_type",
                    "message",
                    "form_location",
                    "consent",
                    "extra_data",
                )
            },
        ),
        (
            "Status & Notes",
            {
                "fields": ("status", "notes"),
            },
        ),
        (
            "Tracking",
            {
                "fields": (
                    "submitted_at",
                    "ip_address",
                    "user_agent",
                    "referrer",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Integration Flags",
            {
                "fields": (
                    "is_duplicate",
                    "sheets_synced",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # -----------------------------------------------------------------------
    # Bulk actions
    # -----------------------------------------------------------------------
    actions = [
        "mark_as_reviewed",
        "mark_as_contacted",
        "mark_as_spam",
        "export_as_csv",
        "retry_sheets_sync",
    ]

    @admin.action(description="Mark selected leads as Reviewed")
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status=Lead.STATUS_REVIEWED)
        self.message_user(request, f"{updated} lead(s) marked as Reviewed.")

    @admin.action(description="Mark selected leads as Contacted")
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(status=Lead.STATUS_CONTACTED)
        self.message_user(request, f"{updated} lead(s) marked as Contacted.")

    @admin.action(description="Mark selected leads as Spam")
    def mark_as_spam(self, request, queryset):
        updated = queryset.update(status=Lead.STATUS_SPAM)
        self.message_user(request, f"{updated} lead(s) marked as Spam.")

    @admin.action(description="Export selected leads to CSV")
    def export_as_csv(self, request, queryset):
        """
        Stream a CSV export of the selected leads.
        Uses Python's built-in csv module with streaming to handle
        large exports without loading everything into memory.
        """

        # Column headers for the CSV
        headers = [
            "Submitted At",
            "Campaign",
            "Full Name",
            "Company",
            "Email",
            "Phone",
            "Country",
            "Industry",
            "Requirement Type",
            "Message",
            "Form Location",
            "Status",
            "Is Duplicate",
            "Files",
            "Notes",
        ]

        def row_generator(qs):
            """Yield the header row then one row per lead."""
            writer = csv.writer(EchoBuffer())
            yield writer.writerow(headers)

            for lead in qs.select_related("campaign").prefetch_related("files"):
                file_names = ", ".join(
                    lead.files.values_list("original_name", flat=True)
                )
                yield writer.writerow([
                    lead.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                    lead.campaign.name,
                    lead.full_name,
                    lead.company,
                    lead.email,
                    lead.phone,
                    lead.country,
                    lead.industry,
                    lead.requirement_type,
                    lead.message,
                    lead.form_location,
                    lead.status,
                    "Yes" if lead.is_duplicate else "No",
                    file_names,
                    lead.notes,
                ])

        response = StreamingHttpResponse(
            row_generator(queryset),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="smec_leads_export.csv"'
        return response

    @admin.action(description="Retry Google Sheets sync for selected leads")
    def retry_sheets_sync(self, request, queryset):
        """Re-push selected leads to Google Sheets."""
        synced = 0
        skipped = 0
        failed = 0

        for lead in queryset.select_related("campaign").prefetch_related("files"):
            if not lead.campaign.sheets_id:
                skipped += 1
                continue

            # Fix 7: Skip leads already synced — pushing again creates duplicate rows.
            if lead.sheets_synced:
                skipped += 1
                continue

            success = push_to_sheets(lead, lead.campaign.sheets_id)
            if success:
                lead.sheets_synced = True
                lead.save(update_fields=["sheets_synced"])
                synced += 1
            else:
                failed += 1

        if synced:
            self.message_user(request, f"Sheets sync successful for {synced} lead(s).")
        if skipped:
            self.message_user(
                request,
                f"{skipped} lead(s) skipped — no Google Sheet configured or already synced.",
                level="warning",
            )
        if failed:
            self.message_user(
                request,
                f"Sheets sync failed for {failed} lead(s). Check server logs.",
                level="warning",
            )
