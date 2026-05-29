#!/bin/bash
# Coral Beacon — first-time setup on a new machine.
# Run from inside the coral-beacon/ directory.
# Usage: bash scripts/setup.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo ""
echo "━━━ Coral Beacon Setup ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Repo: $REPO_DIR"
echo ""

# ── 1. Python venv ────────────────────────────────────────────────
echo "▶ 1/5  Python venv"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "   Created .venv"
fi
source .venv/bin/activate
pip install -q -r requirements.txt
echo "   Dependencies installed"

# ── 2. .env ───────────────────────────────────────────────────────
echo ""
echo "▶ 2/5  .env file"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   Created .env from .env.example"
    echo ""
    echo "   !! Open .env and fill in your API keys, then re-run this script."
    echo "      Required: ANTHROPIC_API_KEY, GITHUB_TOKEN, PAGERDUTY_API_TOKEN,"
    echo "                DATADOG_API_KEY, DATADOG_APP_KEY, STATUSGATOR_API_TOKEN"
    exit 0
fi
set -a && source .env && set +a
echo "   Loaded .env"

# Check required keys are present
MISSING=""
for VAR in ANTHROPIC_API_KEY GITHUB_TOKEN PAGERDUTY_API_TOKEN DATADOG_API_KEY DATADOG_APP_KEY STATUSGATOR_API_TOKEN; do
    if [ -z "${!VAR}" ]; then
        MISSING="$MISSING $VAR"
    fi
done
if [ -n "$MISSING" ]; then
    echo ""
    echo "   !! Missing API keys in .env:$MISSING"
    echo "      Fill them in and re-run."
    exit 1
fi
echo "   All 6 API keys present"

# ── 3. Coral CLI ──────────────────────────────────────────────────
echo ""
echo "▶ 3/5  Coral CLI"
if ! command -v coral &>/dev/null; then
    echo "   Installing coral v0.3.0..."
    mkdir -p "$HOME/.local/bin"
    TMP=$(mktemp -d)
    curl -fsSL \
        "https://github.com/withcoral/coral/releases/download/v0.3.0/coral-x86_64-unknown-linux-gnu.tar.gz" \
        -o "$TMP/coral.tar.gz"
    tar -xzf "$TMP/coral.tar.gz" -C "$HOME/.local/bin/"
    chmod +x "$HOME/.local/bin/coral"
    rm -rf "$TMP"
    export PATH="$HOME/.local/bin:$PATH"
    echo ""
    echo "   Installed. Add this to ~/.bashrc or ~/.zshrc:"
    echo '     export PATH="$HOME/.local/bin:$PATH"'
fi
echo "   $(coral --version 2>&1 | head -1)"

# ── 4. Coral sources ──────────────────────────────────────────────
echo ""
echo "▶ 4/5  Coral sources"

# Use a per-machine config dir alongside the repo
CORAL_CONFIG_DIR="$REPO_DIR/coral-config"
export CORAL_CONFIG_DIR
mkdir -p "$CORAL_CONFIG_DIR"

# Restore the canonical config.toml (no runbook entry — it's registered via --file below)
cat > "$CORAL_CONFIG_DIR/config.toml" << 'TOML'
version = 1

[workspaces.default.sources.datadog]
variables = { DD_SITE = "us5.datadoghq.com" }
secrets = ["DD_API_KEY", "DD_APPLICATION_KEY"]
origin = "bundled"

[workspaces.default.sources.github]
variables = { GITHUB_API_BASE = "https://api.github.com" }
secrets = ["GITHUB_TOKEN"]
origin = "bundled"

[workspaces.default.sources.pagerduty]
variables = {}
secrets = ["PAGERDUTY_API_TOKEN"]
origin = "bundled"

[workspaces.default.sources.statusgator]
variables = {}
secrets = ["STATUSGATOR_API_TOKEN"]
origin = "bundled"
TOML

# Coral's datadog source uses DD_API_KEY / DD_APPLICATION_KEY / DD_SITE
export DD_API_KEY="${DD_API_KEY:-$DATADOG_API_KEY}"
export DD_APPLICATION_KEY="${DD_APPLICATION_KEY:-$DATADOG_APP_KEY}"
export DD_SITE="${DD_SITE:-$DATADOG_SITE}"

# Register all 4 bundled API sources fresh
for SOURCE in pagerduty github datadog statusgator; do
    coral source add "$SOURCE" 2>/dev/null && echo "   $SOURCE registered" \
        || echo "   $SOURCE FAILED — check the API key in .env"
done

# Register Living Runbook custom source (path is machine-specific)
DATA_DIR="$REPO_DIR/data"
mkdir -p "$DATA_DIR"
sed "s|file://CORAL_BEACON_DATA_DIR/|file://${DATA_DIR}/|g" \
    "$REPO_DIR/runbook.yaml" > /tmp/runbook.resolved.yaml
coral source add --file /tmp/runbook.resolved.yaml 2>/dev/null && \
    echo "   runbook registered" || echo "   runbook FAILED"

# Persist CORAL_CONFIG_DIR into .env so the server and seed script use it
if grep -q "^CORAL_CONFIG_DIR=" .env; then
    sed -i "s|^CORAL_CONFIG_DIR=.*|CORAL_CONFIG_DIR=$CORAL_CONFIG_DIR|" .env
else
    echo "CORAL_CONFIG_DIR=$CORAL_CONFIG_DIR" >> .env
fi
echo "   CORAL_CONFIG_DIR=$CORAL_CONFIG_DIR written to .env"

# Quick verify
echo ""
SCHEMAS=$(coral sql "SELECT DISTINCT schema_name FROM coral.tables ORDER BY 1" 2>/dev/null \
    | grep -v "schema_name\|─\|+" | grep -v "^$" | tr -d '| ' | sort | tr '\n' ' ' || true)
echo "   Schemas visible: ${SCHEMAS:-none — check API keys in .env}"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo "━━━ Setup complete ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Verify Coral:"
echo "    coral sql \"SELECT DISTINCT schema_name FROM coral.tables ORDER BY 1\""
echo "    # Should show: datadog github pagerduty runbook statusgator"
echo ""
echo "  Start server:"
echo "    source .venv/bin/activate && set -a && source .env && set +a"
echo "    uvicorn main:app --reload --port 8000"
echo ""
echo "  Seed demo data:  python scripts/seed_demo.py"
echo "  Open UI:         http://localhost:8000"
echo "  Full guide:      cat SETUP.md"
echo ""
