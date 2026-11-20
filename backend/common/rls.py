"""Migration helpers for row level security and append-only tables."""

from django.db import migrations

FUNCTIONS_SQL = """
CREATE OR REPLACE FUNCTION pointqr_current_tenant() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.current_tenant', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION pointqr_is_platform() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT coalesce(current_setting('app.platform_admin', true), '') = 'on'
$$;

CREATE OR REPLACE FUNCTION pointqr_forbid_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'table % is append-only (% refused)', TG_TABLE_NAME, TG_OP
    USING ERRCODE = 'insufficient_privilege';
END
$$;
"""

DROP_FUNCTIONS_SQL = """
DROP FUNCTION IF EXISTS pointqr_forbid_change();
DROP FUNCTION IF EXISTS pointqr_is_platform();
DROP FUNCTION IF EXISTS pointqr_current_tenant();
"""


def _policies_sql(table: str, *, null_rows: str | None) -> str:
    """``null_rows``: None (company always set), "shared" (NULL rows are reference data readable by
    every tenant, e.g. national holidays) or "platform" (NULL rows belong to the editor team)."""
    tenant = "company_id = pointqr_current_tenant()"
    write = tenant
    if null_rows == "shared":
        read = f"({tenant} OR company_id IS NULL OR pointqr_is_platform())"
        write = f"({tenant} OR (company_id IS NULL AND pointqr_is_platform()))"
    elif null_rows == "platform":
        read = f"({tenant} OR pointqr_is_platform())"
        write = f"({tenant} OR (company_id IS NULL AND pointqr_is_platform()))"
    else:
        read = f"({tenant} OR pointqr_is_platform())"
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY pq_select ON {table} FOR SELECT USING {read};
CREATE POLICY pq_insert ON {table} FOR INSERT WITH CHECK ({write});
CREATE POLICY pq_update ON {table} FOR UPDATE USING ({write}) WITH CHECK ({write});
CREATE POLICY pq_delete ON {table} FOR DELETE USING ({write});
"""


def _drop_policies_sql(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS pq_select ON {table};
DROP POLICY IF EXISTS pq_insert ON {table};
DROP POLICY IF EXISTS pq_update ON {table};
DROP POLICY IF EXISTS pq_delete ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


def enable_rls(*tables: str, null_rows: str | None = None) -> list[migrations.RunSQL]:
    return [
        migrations.RunSQL(_policies_sql(t, null_rows=null_rows), _drop_policies_sql(t))
        for t in tables
    ]


def append_only(*tables: str) -> list[migrations.RunSQL]:
    return [
        migrations.RunSQL(
            f"CREATE TRIGGER pq_append_only BEFORE UPDATE OR DELETE ON {t} "
            f"FOR EACH ROW EXECUTE FUNCTION pointqr_forbid_change();",
            f"DROP TRIGGER IF EXISTS pq_append_only ON {t};",
        )
        for t in tables
    ]
