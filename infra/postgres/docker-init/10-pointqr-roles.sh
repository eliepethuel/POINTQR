#!/bin/sh
# First start of the postgres container: database + owner and runtime roles (ADR-0004).
# Reuses infra/postgres/create-roles.sql, the script of the native setup.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v db="$POINTQR_DB" \
  -v owner_user="$POINTQR_OWNER_USER" -v owner_password="$POINTQR_OWNER_PASSWORD" \
  -v app_user="$POINTQR_APP_USER" -v app_password="$POINTQR_APP_PASSWORD" \
  -f /pointqr/create-roles.sql
