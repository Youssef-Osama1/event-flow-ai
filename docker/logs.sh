#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mapfile -t services < <(docker compose config --services)
echo "Services:"
for i in "${!services[@]}"; do echo "  $((i + 1))) ${services[$i]}"; done
echo "  a) all"
read -rp "Show logs for: " choice
if [ "$choice" = "a" ]; then
  docker compose logs -f --tail=200
else
  docker compose logs -f --tail=200 "${services[$((choice - 1))]}"
fi
