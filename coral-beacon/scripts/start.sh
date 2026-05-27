#!/bin/bash
set -e

# Register the Living Runbook custom source if not already in config
CORAL_CONFIG_DIR="${CORAL_CONFIG_DIR:-/app/coral-config}"
export CORAL_CONFIG_DIR

coral source add --file /app/runbook.yaml 2>/dev/null || true

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
