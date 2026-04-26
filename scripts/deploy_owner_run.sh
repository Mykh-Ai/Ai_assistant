#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/bot/repo}"

cd "$ROOT_DIR"

mkdir -p /bot/data/storage /bot/logs /bot/backups /bot/tenants

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
