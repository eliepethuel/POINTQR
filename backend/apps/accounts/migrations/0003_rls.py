from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security for this app's tables (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("accounts", "0002_initial")]

    operations = [
        *enable_rls("accounts_user", null_rows="platform"),
    ]