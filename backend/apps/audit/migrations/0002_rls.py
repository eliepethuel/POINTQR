from django.db import migrations

from common.rls import append_only, enable_rls


class Migration(migrations.Migration):
    """Row level security for this app's tables (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("audit", "0001_initial")]

    operations = [
        *enable_rls("audit_auditlog", null_rows="platform"),
        *append_only("audit_auditlog"),
    ]