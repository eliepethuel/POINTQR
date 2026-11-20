from django.db import migrations

from common.rls import DROP_FUNCTIONS_SQL, FUNCTIONS_SQL


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [migrations.RunSQL(FUNCTIONS_SQL, DROP_FUNCTIONS_SQL)]
