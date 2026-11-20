from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security for this app's tables (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("schedules", "0001_initial")]

    operations = [
        *enable_rls(
            "schedules_schedule", "schedules_scheduleassignment", "schedules_scheduleexception"
        ),
        *enable_rls("schedules_publicholiday", null_rows="shared"),
    ]