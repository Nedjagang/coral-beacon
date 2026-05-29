#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${CORAL_BEACON_DATA_DIR:-$REPO_DIR/data}"
export CORAL_CONFIG_DIR="${CORAL_CONFIG_DIR:-/app/coral-config}"

# Register the Living Runbook custom source with the correct data path
sed "s|file://CORAL_BEACON_DATA_DIR/|file://${DATA_DIR}/|g" \
    "$REPO_DIR/runbook.yaml" > /tmp/runbook.resolved.yaml
coral source add --file /tmp/runbook.resolved.yaml 2>/dev/null || true

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
