"""
leads/migrations/0001_initial.py

Initial migration for the leads app.
Creates Lead and RFQFile tables.
Depends on campaigns/0001_initial.
"""

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models
import leads.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("campaigns", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("full_name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("message", models.TextField()),
                ("consent", models.BooleanField(default=False)),
                ("company", models.CharField(blank=True, max_length=200)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("requirement_type", models.CharField(blank=True, max_length=100)),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                ("form_location", models.CharField(blank=True, max_length=50)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("referrer", models.URLField(blank=True, max_length=500)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("reviewed", "Reviewed"),
                            ("contacted", "Contacted"),
                            ("quoted", "Quoted"),
                            ("closed", "Closed"),
                            ("spam", "Spam"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("is_duplicate", models.BooleanField(default=False)),
                ("sheets_synced", models.BooleanField(default=False)),
                ("sales_email_sent", models.BooleanField(default=False)),
                ("reply_email_sent", models.BooleanField(default=False)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="leads",
                        to="campaigns.campaign",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lead",
                "verbose_name_plural": "Leads",
                "ordering": ["-submitted_at"],
            },
        ),
        migrations.CreateModel(
            name="RFQFile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file",
                    models.FileField(upload_to=leads.models.rfq_upload_path),
                ),
                ("original_name", models.CharField(max_length=255)),
                ("file_size", models.PositiveIntegerField()),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="leads.lead",
                    ),
                ),
            ],
            options={
                "verbose_name": "RFQ File",
                "verbose_name_plural": "RFQ Files",
                "ordering": ["uploaded_at"],
            },
        ),
    ]
