from django.db import migrations

GUARD = """
CREATE OR REPLACE FUNCTION pointqr_checkin_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- Only the retention job (ENF-04) may touch check-ins, and only to remove raw GPS
  -- or delete rows past the retention period. Everything else is refused (RG-12).
  IF coalesce(current_setting('app.retention_purge', true), '') = 'on' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    IF NEW.latitude IS NULL AND NEW.longitude IS NULL
       AND ROW(NEW.id, NEW.agent_id, NEW.effective_ts, NEW.server_ts, NEW.direction, NEW.result,
               NEW.refusal_code, NEW.corrects_id)
           IS NOT DISTINCT FROM
           ROW(OLD.id, OLD.agent_id, OLD.effective_ts, OLD.server_ts, OLD.direction, OLD.result,
               OLD.refusal_code, OLD.corrects_id) THEN
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION 'table % is append-only (% refused)', TG_TABLE_NAME, TG_OP
    USING ERRCODE = 'insufficient_privilege';
END
$$;
DROP TRIGGER IF EXISTS pq_append_only ON attendance_checkin;
CREATE TRIGGER pq_append_only BEFORE UPDATE OR DELETE ON attendance_checkin
  FOR EACH ROW EXECUTE FUNCTION pointqr_checkin_guard();
"""

REVERSE = """
DROP TRIGGER IF EXISTS pq_append_only ON attendance_checkin;
CREATE TRIGGER pq_append_only BEFORE UPDATE OR DELETE ON attendance_checkin
  FOR EACH ROW EXECUTE FUNCTION pointqr_forbid_change();
DROP FUNCTION IF EXISTS pointqr_checkin_guard();
"""


class Migration(migrations.Migration):
    """Check-ins stay append-only, except for the retention purge (ENF-04)."""

    dependencies = [("attendance", "0005_rls_days")]

    operations = [migrations.RunSQL(GUARD, REVERSE)]
