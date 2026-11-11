#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "Missing docker/.env. Copy docker/.env.example to docker/.env first."
  exit 1
fi
set -a; . ./.env; set +a
NETWORK="${PROJECT_NAME:-eventflow}-network"
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"
docker compose up -d --build "$@"
docker compose ps
