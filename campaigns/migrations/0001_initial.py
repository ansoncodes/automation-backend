"""
campaigns/migrations/0001_initial.py

Initial migration for the campaigns app.
Creates the Campaign table with all fields.
"""

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Campaign",
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
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(unique=True)),
                (
                    "api_key",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        help_text="Auto-generated UUID. Embed this in the static HTML form as SMEC_CONFIG.apiKey.",
                    ),
                ),
                ("url", models.URLField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "notify_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        help_text="Sales notification email for this campaign. Falls back to SALES_EMAIL setting if blank.",
                    ),
                ),
                (
                    "sheets_id",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        help_text="Google Sheets spreadsheet ID (from the sheet URL). Leave blank to skip.",
                    ),
                ),
                (
                    "fields_config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text='Controls which optional fields are required/optional/hidden for this campaign.',
                    ),
                ),
            ],
            options={
                "verbose_name": "Campaign",
                "verbose_name_plural": "Campaigns",
                "ordering": ["name"],
            },
        ),
    ]
