<#
.SYNOPSIS
  PointQR developer commands for Windows, native toolchain (ADR-0010). Same targets as the Makefile.
.DESCRIPTION
  Prerequisites: uv, Node 24+, PostgreSQL 16, Garnet (Redis protocol).
    env       create .env with random secrets
    db-init   create database and roles (asks for the PostgreSQL superuser password)
    db-reset  development only: drop and recreate the schema
    install   install backend and frontend dependencies
    migrate   apply database migrations (owner role)
    dev       start Garnet, API, Celery worker + beat and Angular, each in its own window
    api | worker | beat | front | redis   start one process in the current window
    test | test-back | test-front | lint | lint-back | lint-front | format
    openapi   export backend/openapi.yaml
    client    regenerate the typed Angular client from the schema
    seed      load demo data
    docker-up | docker-down | docker-seed   full stack in containers on :8080 (ADR-0014)
.EXAMPLE
  .\tasks.ps1 env; .\tasks.ps1 db-init; .\tasks.ps1 install; .\tasks.ps1 migrate; .\tasks.ps1 dev
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('env', 'db-init', 'db-reset', 'install', 'migrate', 'dev', 'api', 'worker', 'beat', 'front',
    'redis', 'shell', 'seed', 'test', 'test-back', 'test-front', 'lint', 'lint-back', 'lint-front',
    'format', 'openapi', 'client', 'e2e', 'docker-up', 'docker-down', 'docker-seed', 'help')]
  [string]$Target = 'help'
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

function Invoke-Checked([string]$Dir, [scriptblock]$Block) {
  Push-Location $Dir
  # Native tools write warnings to stderr: never turn them into terminating errors.
  $ErrorActionPreference = 'Continue'
  try {
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
  } finally { Pop-Location }
}

function New-Secret([int]$Length = 40) {
  -join ((48..57) + (97..122) | Get-Random -Count $Length | ForEach-Object { [char]$_ })
}

function New-FernetKey {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}

function Read-DotEnv {
  $values = @{}
  foreach ($line in Get-Content (Join-Path $Root '.env')) {
    if ($line -match '^\s*([A-Z0-9_]+)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
  }
  $values
}

function Initialize-Env {
  $path = Join-Path $Root '.env'
  if (Test-Path $path) { Write-Host '.env already exists.'; return }
  $text = (Get-Content (Join-Path $Root '.env.example') -Raw).
    Replace('change-me-with-50-random-characters', (New-Secret 64)).
    Replace('change-me-owner', (New-Secret)).
    Replace('change-me-app', (New-Secret)).
    Replace('change-me-superuser', (New-Secret)).
    Replace('FIELD_ENCRYPTION_KEY=', "FIELD_ENCRYPTION_KEY=$(New-FernetKey)")
  [IO.File]::WriteAllText($path, $text)  # UTF-8 without BOM
  Write-Host '.env created with random secrets.'
}

function Find-Psql {
  $cmd = Get-Command psql -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $candidate = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $candidate) { throw 'psql not found: install PostgreSQL 16 first.' }
  $candidate.FullName
}

function Initialize-Database {
  $ErrorActionPreference = 'Continue'
  $cfg = Read-DotEnv
  $psql = Find-Psql
  $superUser = Read-Host 'PostgreSQL superuser (default: postgres)'
  if (-not $superUser) { $superUser = 'postgres' }
  & $psql -h $cfg.POSTGRES_HOST -p $cfg.POSTGRES_PORT -U $superUser -d postgres `
    -v "db=$($cfg.POSTGRES_DB)" `
    -v "owner_user=$($cfg.POSTGRES_OWNER_USER)" -v "owner_password=$($cfg.POSTGRES_OWNER_PASSWORD)" `
    -v "app_user=$($cfg.APP_DB_USER)" -v "app_password=$($cfg.APP_DB_PASSWORD)" `
    -f (Join-Path $Root 'infra\postgres\create-roles.sql')
  if ($LASTEXITCODE -ne 0) { throw 'Database initialisation failed.' }
  Write-Host 'Database and roles ready.'
}

function Reset-Database {
  $ErrorActionPreference = 'Continue'
  # Development only: drops every table, then migrations rebuild the schema (owner role, no superuser).
  $cfg = Read-DotEnv
  $psql = Find-Psql
  $env:PGPASSWORD = $cfg.POSTGRES_OWNER_PASSWORD
  try {
    $sql = @"
SET client_min_messages = warning;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO "$($cfg.APP_DB_USER)";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "$($cfg.APP_DB_USER)";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "$($cfg.APP_DB_USER)";
"@
    $sql | & $psql -h $cfg.POSTGRES_HOST -p $cfg.POSTGRES_PORT -U $cfg.POSTGRES_OWNER_USER -d $cfg.POSTGRES_DB -v ON_ERROR_STOP=1 -q
    if ($LASTEXITCODE -ne 0) { throw 'Database reset failed.' }
  } finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
  Write-Host 'Schema dropped and recreated. Run: .\tasks.ps1 migrate'
}

# Runs a backend command with the owner role (migrations, tests create/alter tables).
function Invoke-BackendAsOwner([string[]]$Arguments, [string]$Settings = 'config.settings.dev') {
  $cfg = Read-DotEnv
  $env:DATABASE_URL = $cfg.MIGRATION_DATABASE_URL
  $env:DJANGO_SETTINGS_MODULE = $Settings
  try { Invoke-Checked $Backend { uv run @Arguments } }
  finally { Remove-Item Env:DATABASE_URL, Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue }
}

function Start-InWindow([string]$Title, [string]$TaskName) {
  Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle='PointQR $Title'; & '$PSCommandPath' $TaskName"
  )
}

function Start-Garnet {
  $garnet = Get-Command garnet-server -ErrorAction SilentlyContinue
  if (-not $garnet) { throw 'garnet-server not found: dotnet tool install --global garnet-server' }
  # --lua: Celery (kombu) relies on Lua scripts, disabled by default in Garnet.
  & $garnet.Source --port 6379 --lua
}

switch ($Target) {
  'env'        { Initialize-Env }
  'db-init'    { Initialize-Database }
  'db-reset'   { Reset-Database }
  'install'    {
    Invoke-Checked $Backend { uv sync --frozen }
    Invoke-Checked $Frontend { npm ci --no-audit --no-fund }
  }
  'migrate'    { Invoke-BackendAsOwner @('python', 'manage.py', 'migrate', '--noinput') }
  'dev'        {
    Start-InWindow 'redis' 'redis'
    Start-InWindow 'api' 'api'
    Start-InWindow 'worker' 'worker'
    Start-InWindow 'beat' 'beat'
    Start-InWindow 'front' 'front'
    Write-Host 'Front: http://localhost:4200   API docs: http://localhost:8000/api/docs/'
  }
  'redis'      { Start-Garnet }
  'api'        { Invoke-Checked $Backend { uv run uvicorn config.asgi:application --reload --port 8000 } }
  'worker'     { Invoke-Checked $Backend { uv run celery -A config worker -l info --pool=solo --without-mingle --without-gossip } }
  'beat'       { Invoke-Checked $Backend { uv run celery -A config beat -l info } }
  'front'      { Invoke-Checked $Frontend { npm start } }
  'shell'      { Invoke-Checked $Backend { uv run python manage.py shell } }
  'seed'       { Invoke-BackendAsOwner @('python', 'manage.py', 'seed_demo') }
  'test-back'  {
    Invoke-BackendAsOwner @('pytest', '--cov', '--cov-report=term-missing:skip-covered') 'config.settings.test'
  }
  'test-front' { Invoke-Checked $Frontend { npm test -- --watch=false } }
  'test'       { & $PSCommandPath test-back; & $PSCommandPath test-front }
  'lint-back'  {
    Invoke-Checked $Backend { uv run ruff check .; if ($LASTEXITCODE -eq 0) { uv run ruff format --check . } }
    Invoke-Checked $Backend { uv run mypy . }
  }
  'lint-front' { Invoke-Checked $Frontend { npm run lint; if ($LASTEXITCODE -eq 0) { npm run format:check } } }
  'lint'       { & $PSCommandPath lint-back; & $PSCommandPath lint-front }
  'format'     {
    Invoke-Checked $Backend { uv run ruff check --fix .; uv run ruff format . }
    Invoke-Checked $Frontend { npm run format }
  }
  'openapi'    {
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.test'
    try { Invoke-Checked $Backend { uv run python manage.py spectacular --file openapi.yaml --validate } }
    finally { Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue }
  }
  'client'     { & $PSCommandPath openapi; Invoke-Checked $Frontend { npm run api:generate } }
  'e2e'        { Invoke-Checked $Frontend { npx playwright test } }
  'docker-up'  { Invoke-Checked $Root { docker compose up -d --build } }
  'docker-down' { Invoke-Checked $Root { docker compose down } }
  'docker-seed' { Invoke-Checked $Root { docker compose --profile demo run --rm seed } }
  default      { Get-Help $PSCommandPath -Detailed }
}
