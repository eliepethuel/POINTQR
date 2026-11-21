#!/bin/sh
# Creates .env from .env.example with random secrets (Linux, macOS, CI).
set -eu
cd "$(dirname "$0")/../.."
[ -f .env ] && { echo ".env already exists"; exit 0; }

secret() { LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c "$1"; }
fernet() { head -c 32 /dev/urandom | base64 | tr '+/' '-_'; }

sed \
  -e "s/change-me-with-50-random-characters/$(secret 64)/" \
  -e "s/change-me-owner/$(secret 32)/g" \
  -e "s/change-me-app/$(secret 32)/g" \
  -e "s/change-me-superuser/$(secret 32)/g" \
  -e "s/change-me-s3-access/$(secret 20)/g" \
  -e "s/change-me-s3-secret/$(secret 40)/g" \
  -e "s|^FIELD_ENCRYPTION_KEY=$|FIELD_ENCRYPTION_KEY=$(fernet)|" \
  .env.example > .env
echo ".env created with random secrets."
