"""
Cron trigger view.

Accepts GET requests with a ?token= query parameter authenticated against
the CRON_SECRET environment variable, then runs the scheduled task logic.
"""

import os
import logging

from django.http import JsonResponse
from django.views import View

from cron.tasks import run_task

logger = logging.getLogger(__name__)


class RunCronTaskView(View):
    """
    GET /cron/run/?token=<CRON_SECRET>

    Validates the token and executes the scheduled task.
    """

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        token = request.GET.get("token", "")

        expected_token = os.environ.get("CRON_SECRET")
        if not expected_token or token != expected_token:
            logger.warning("Cron trigger rejected — invalid or missing token.")
            return JsonResponse({"error": "unauthorized"}, status=401)

        try:
            logger.info("Cron trigger authorised. Running task...")
            run_task()
            logger.info("Cron task completed successfully.")
            return JsonResponse({"status": "ok", "message": "task completed"})
        except Exception as e:
            logger.exception("Cron task failed: %s", e)
            return JsonResponse({"error": "failed", "detail": str(e)}, status=500)