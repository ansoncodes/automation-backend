"""
leads/models.py

Defines the Lead and RFQFile models.

Lead — one record per form submission. Contains all the data collected
from the RFQ form plus metadata (IP, user agent, referrer) and tracking
flags (email sent, duplicate).

RFQFile — one record per uploaded attachment, linked to a Lead via FK.
Files are stored using Django's file storage backend (local in dev, S3 in prod).

The extra_data JSONField allows future campaigns to collect unique fields
without requiring a database migration.
"""

from django.db import models
from campaigns.models import Campaign


def rfq_upload_path(instance, filename):
    """
    Return a unique upload path for each RFQ attachment.
    Files are grouped by lead ID:  rfq_files/<lead_id>/<filename>

    NOTE: At the time this function is called during RFQFile.save(),
    instance.lead should already be saved so instance.lead.id is available.
    """
    return f"rfq_files/{instance.lead.id}/{filename}"


class Lead(models.Model):
    """
    A single RFQ form submission from any SMEC landing page.

    Status lifecycle: new → reviewed → contacted → quoted → closed
                      (any status can be set to spam)
    """

    STATUS_NEW = "new"
    STATUS_REVIEWED = "reviewed"
    STATUS_CONTACTED = "contacted"
    STATUS_QUOTED = "quoted"
    STATUS_CLOSED = "closed"
    STATUS_SPAM = "spam"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_CONTACTED, "Contacted"),
        (STATUS_QUOTED, "Quoted"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_SPAM, "Spam"),
    ]

    # ------------------------------------------------------------------
    # Campaign relationship
    # ------------------------------------------------------------------
    campaign = models.ForeignKey(
        Campaign,
        related_name="leads",
        on_delete=models.PROTECT,  # don't delete campaign if leads exist
        help_text="The campaign (landing page) this lead came from",
    )

    # ------------------------------------------------------------------
    # Core required fields — always present on every submission
    # ------------------------------------------------------------------
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    consent = models.BooleanField(
        default=False,
        help_text="True if the lead explicitly consented to being contacted",
    )

    # ------------------------------------------------------------------
    # Optional fields — presence/requirement controlled by fields_config
    # ------------------------------------------------------------------
    company = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    requirement_type = models.CharField(max_length=100, blank=True)

    # ------------------------------------------------------------------
    # Overflow field — stores any extra data without a migration
    # ------------------------------------------------------------------
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra form fields not mapped to core columns (future campaigns)",
    )

    # ------------------------------------------------------------------
    # Tracking / analytics metadata
    # ------------------------------------------------------------------
    form_location = models.CharField(
        max_length=50,
        blank=True,
        help_text="Which form on the page: hero | popup | footer | etc.",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True, max_length=500)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # ------------------------------------------------------------------
    # Status & workflow
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal sales notes — not visible to the lead",
    )

    # ------------------------------------------------------------------
    # Flags — updated asynchronously after save
    # ------------------------------------------------------------------
    is_duplicate = models.BooleanField(
        default=False,
        help_text="True if another lead with the same email+campaign exists in the last 24 hours",
    )

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"{self.full_name} ({self.email}) — {self.campaign.name}"

    def get_file_names(self):
        """Return a comma-separated string of all attached file names."""
        names = self.files.values_list("original_name", flat=True)
        return ", ".join(names) if names else "None"


class RFQFile(models.Model):
    """
    A single file attachment uploaded alongside an RFQ form submission.

    One Lead can have many RFQFiles (up to the limit defined in validators.py).
    The file itself is stored via Django's storage backend (local or S3).
    """

    lead = models.ForeignKey(
        Lead,
        related_name="files",
        on_delete=models.CASCADE,  # delete files when lead is deleted
    )
    file = models.FileField(upload_to=rfq_upload_path)
    original_name = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by the user",
    )
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "RFQ File"
        verbose_name_plural = "RFQ Files"

    def __str__(self):
        return f"{self.original_name} ({self.file_size} bytes)"
