from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("attendance", "0004_period_workday")]

    operations = [*enable_rls("attendance_workday", "attendance_period")]
