from typing import Any

from django.db import migrations

YEARS = (2026, 2027)


def load(apps: Any, schema_editor: Any) -> None:
    from apps.schedules.holidays import cote_divoire_holidays

    with schema_editor.connection.cursor() as cursor:
        # Reference rows (company NULL) are written in the platform scope (RLS policy).
        cursor.execute("SELECT set_config('app.platform_admin', 'on', true)")
    holiday = apps.get_model("schedules", "PublicHoliday")
    for year in YEARS:
        for day, label in cote_divoire_holidays(year):
            holiday.objects.get_or_create(
                company=None, date=day, country="CI", defaults={"label": label}
            )


def unload(apps: Any, schema_editor: Any) -> None:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.platform_admin', 'on', true)")
    apps.get_model("schedules", "PublicHoliday").objects.filter(
        company=None, date__year__in=YEARS
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("schedules", "0002_rls")]

    operations = [migrations.RunPython(load, unload)]
