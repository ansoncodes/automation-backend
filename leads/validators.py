"""
leads/validators.py

File validation logic for RFQ attachments.

validate_rfq_files() is called from the submit view before saving any files.
It checks:
  - Number of files (max 5 per submission)
  - File size (max 10 MB per file)
  - Allowed file extensions
"""

from rest_framework.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_FILE_COUNT = 5
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

# Plain set of allowed file extensions (lowercase, no leading dot).
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "zip", "dwg",
    "jpg", "jpeg", "png",
}


def validate_rfq_files(files):
    """
    Validate a list of uploaded files for the RFQ form.

    Args:
        files: list of InMemoryUploadedFile / TemporaryUploadedFile objects
               (from request.FILES.getlist("rfq_files"))

    Raises:
        ValidationError: with a descriptive message for any violation.

    Returns:
        None if all files pass validation.
    """
    if not files:
        return  # no files uploaded — that's fine

    # ------------------------------------------------------------------
    # 1. Count limit
    # ------------------------------------------------------------------
    if len(files) > MAX_FILE_COUNT:
        raise ValidationError(
            f"You can upload a maximum of {MAX_FILE_COUNT} files per submission. "
            f"You submitted {len(files)}."
        )

    for f in files:
        # --------------------------------------------------------------
        # 2. File size limit
        # --------------------------------------------------------------
        if f.size > MAX_FILE_SIZE:
            size_mb = f.size / (1024 * 1024)
            raise ValidationError(
                f"'{f.name}' is {size_mb:.1f} MB. "
                f"Maximum allowed size is {MAX_FILE_SIZE // (1024 * 1024)} MB per file."
            )

        # --------------------------------------------------------------
        # 3. Extension whitelist
        # --------------------------------------------------------------
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"'{f.name}' has an unsupported file type (.{ext}). "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )
