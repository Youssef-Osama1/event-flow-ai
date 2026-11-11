#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
read -rp "Migration message: " message
uv run alembic revision --autogenerate -m "$message"
