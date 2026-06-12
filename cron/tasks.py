"""
Scheduled task logic for the cron app.

All cron-triggered business logic lives here so the view stays clean.
Add your recurring tasks in the run_task() function.
"""

import logging

logger = logging.getLogger(__name__)


def run_task() -> None:
    """
    Main entry point called by the cron view.

    Place all scheduled work here — e.g. sending daily digests,
    cleaning up stale records, syncing data, etc.
    """
    logger.info("Cron task started.")

    # ──────────────────────────────────────────────────────────────────────
    # Add your scheduled logic below.
    # Example:
    #
    #   from leads.models import Lead
    #   stale = Lead.objects.filter(status="pending", created_at__lt=one_day_ago)
    #   count = stale.update(status="expired")
    #   logger.info("Expired %d stale leads.", count)
    #
    # ──────────────────────────────────────────────────────────────────────

    logger.info("Cron task completed successfully.")