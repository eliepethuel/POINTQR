from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security for this app's tables (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("organization", "0002_initial")]

    operations = [
        *enable_rls(
            "organization_site",
            "organization_orgunit",
            "organization_agent",
            "organization_device",
            "organization_devicechangerequest",
        ),
    ]