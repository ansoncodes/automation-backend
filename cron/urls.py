from django.urls import path

from cron.views import RunCronTaskView

urlpatterns = [
    path("run/", RunCronTaskView.as_view(), name="cron-run"),
]