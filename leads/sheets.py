"""
leads/sheets.py

Google Sheets integration for SMEC lead capture.

push_to_sheets() appends a new row to the Google Sheet associated with
a campaign whenever a lead is successfully saved.

Setup requirements:
  1. Create a Google Cloud service account with Sheets API enabled.
  2. Download the JSON key file and set GOOGLE_SERVICE_ACCOUNT_JSON in .env
     to the path of that file.
  3. Share the target Google Sheet with the service account email address
     (give it Editor access).
  4. Copy the sheet's spreadsheet ID from its URL and paste it into the
     Campaign's sheets_id field in the admin panel.

The spreadsheet ID is the long string in the Google Sheets URL:
  https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit

Failure behaviour:
  - All exceptions are caught and logged.
  - push_to_sheets() returns False on any error.
  - The view never raises an exception from this function.
  - A sheets sync failure does NOT fail the lead submission.

To move to Celery in the future:
  - Wrap this function call in a Celery task
  - No changes to push_to_sheets() itself are required
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Google Sheets API scopes required for appending rows
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def push_to_sheets(lead, sheet_id: str) -> bool:
    """
    Append a lead record as a new row in the given Google Sheet.

    The first row of the sheet should contain these column headers
    (the function does not create them automatically):
      Submitted At | Campaign | Name | Company | Email | Phone | Country |
      Industry | Requirement Type | Message | Form Location | Files |
      Duplicate | Status | Lead ID

    Args:
        lead:     Lead model instance (files should already be saved)
        sheet_id: Google Spreadsheet ID (from the sheet's URL)

    Returns:
        True on success, False on any error.
    """
    try:
        # ------------------------------------------------------------------
        # Import here to avoid import errors if gspread is not installed
        # (e.g. when running only development.txt which includes gspread)
        # ------------------------------------------------------------------
        import gspread
        from google.oauth2.service_account import Credentials

        # ------------------------------------------------------------------
        # Load credentials from the service account JSON key file
        # ------------------------------------------------------------------
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=SCOPES,
        )

        # ------------------------------------------------------------------
        # Authorise and open the spreadsheet
        # ------------------------------------------------------------------
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        sheet = spreadsheet.sheet1  # always write to the first worksheet

        # ------------------------------------------------------------------
        # Build the row data
        # All values are converted to strings to avoid Sheets type issues.
        # ------------------------------------------------------------------
        file_names = ", ".join(
            lead.files.values_list("original_name", flat=True)
        ) or ""

        row = [
            str(lead.submitted_at.strftime("%Y-%m-%d %H:%M:%S")),
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
            file_names,
            "Yes" if lead.is_duplicate else "No",
            lead.status,
            str(lead.id),
        ]

        # ------------------------------------------------------------------
        # Append the row to the end of the sheet
        # ------------------------------------------------------------------
        sheet.append_row(row, value_input_option="USER_ENTERED")

        logger.info(
            "Lead %s successfully synced to Google Sheet %s",
            lead.id,
            sheet_id,
        )
        return True

    except Exception as exc:
        logger.error(
            "Google Sheets sync failed for lead %s (sheet=%s): %s",
            lead.id,
            sheet_id,
            exc,
            exc_info=True,
        )
        return False
