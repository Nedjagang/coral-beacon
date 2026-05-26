#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUERY_FILE="${1:?Usage: ./scripts/run_coral_query.sh queries/foo.sql}"

export CORAL_CONFIG_DIR="${CORAL_CONFIG_DIR:-$HOME/coral-hackathon}"
coral sql "$(cat "$ROOT/$QUERY_FILE")"
