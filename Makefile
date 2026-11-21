# PointQR developer commands (Linux, macOS, CI), native toolchain (ADR-0010).
# Windows: .\tasks.ps1 <target>
SHELL := /bin/sh
include $(wildcard .env)
export

OWNER_DB = DATABASE_URL=$(MIGRATION_DATABASE_URL)

.PHONY: env db-init install migrate api worker beat front test test-back test-front lint lint-back \
        lint-front format openapi client seed e2e docker-up docker-down docker-seed

env:
	@./infra/scripts/init-env.sh

db-init:
	psql -h $(POSTGRES_HOST) -p $(POSTGRES_PORT) -U postgres -d postgres \
	  -v db=$(POSTGRES_DB) -v owner_user=$(POSTGRES_OWNER_USER) -v owner_password=$(POSTGRES_OWNER_PASSWORD) \
	  -v app_user=$(APP_DB_USER) -v app_password=$(APP_DB_PASSWORD) -f infra/postgres/create-roles.sql

install:
	cd backend && uv sync --frozen
	cd frontend && npm ci --no-audit --no-fund

migrate:
	cd backend && $(OWNER_DB) uv run python manage.py migrate --noinput

api:
	cd backend && uv run uvicorn config.asgi:application --reload --port 8000

worker:
	cd backend && uv run celery -A config worker -l info

beat:
	cd backend && uv run celery -A config beat -l info

front:
	cd frontend && npm start

seed:
	cd backend && $(OWNER_DB) uv run python manage.py seed_demo

test: test-back test-front

test-back:
	cd backend && $(OWNER_DB) DJANGO_SETTINGS_MODULE=config.settings.test \
	  uv run pytest --cov --cov-report=term-missing:skip-covered

test-front:
	cd frontend && npm test -- --watch=false

lint: lint-back lint-front

lint-back:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy .

lint-front:
	cd frontend && npm run lint && npm run format:check

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && npm run format

openapi:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.test \
	  uv run python manage.py spectacular --file openapi.yaml --validate

client: openapi
	cd frontend && npm run api:generate

e2e:
	cd frontend && npx playwright test

# Full stack in containers on http://localhost:8080 (ADR-0014)
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-seed:
	docker compose --profile demo run --rm seed
