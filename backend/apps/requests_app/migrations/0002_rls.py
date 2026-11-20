from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("requests_app", "0001_initial")]

    operations = [*enable_rls("requests_app_request", "requests_app_requestdecision")]
