from django.db import migrations

from common.rls import append_only, enable_rls


class Migration(migrations.Migration):
    """Check-ins: row level security and append-only trigger (RG-12, ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("attendance", "0002_initial")]

    operations = [
        *enable_rls("attendance_checkin"),
        *append_only("attendance_checkin"),
    ]
