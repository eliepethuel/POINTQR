from django.db import migrations

from common.rls import enable_rls


class Migration(migrations.Migration):
    """Row level security (ADR-0004)."""

    dependencies = [("common", "0001_rls_functions"), ("kiosks", "0001_initial")]

    operations = [
        *enable_rls("kiosks_kiosk", "kiosks_kioskpairingcode"),
    ]
