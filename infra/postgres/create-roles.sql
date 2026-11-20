-- Creates the PointQR database and its two roles (ADR-0004). Idempotent.
-- Run as a PostgreSQL superuser through `tasks.ps1 db-init` / `make db-init`, which pass:
--   -v db=... -v owner_user=... -v owner_password=... -v app_user=... -v app_password=...
--
--   owner : owns the schema, runs migrations and tests (CREATEDB for the test database).
--   app   : runtime role, neither superuser nor BYPASSRLS: row level security always applies.
\set ON_ERROR_STOP on

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L CREATEDB NOSUPERUSER NOCREATEROLE NOBYPASSRLS',
              :'owner_user', :'owner_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'owner_user') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
              :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec

SELECT format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8''', :'db', :'owner_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec

\connect :db

GRANT CONNECT ON DATABASE :"db" TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";
