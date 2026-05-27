# Coral Beacon — Deployment Guide

> Read `ARCHITECTURE.md` first for how the app works. This file covers deploying it.

---

## Requirements for any deployment target

1. **Python 3.12+** with `pip install -r requirements.txt`
2. **Coral binary** (`coral`) in `PATH` — download `coral-x86_64-unknown-linux-gnu.tar.gz` from [GitHub releases](https://github.com/withcoral/coral/releases)
3. **`CORAL_CONFIG_DIR`** pointing to a directory with `config.toml` and the `runbook` source registered
4. **Six env vars** set: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `PAGERDUTY_API_TOKEN`, `DATADOG_API_KEY`, `DATADOG_APP_KEY`, `STATUSGATOR_API_TOKEN`
5. **Writable filesystem** at `data/` — the agent appends to `runbook.jsonl` and writes `latest_investigation.json`

---

## Docker (used for Railway / Fly / Render)

### Build and run locally

```bash
cd coral-beacon
docker build -t coral-beacon .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e GITHUB_TOKEN=github_pat_... \
  -e PAGERDUTY_API_TOKEN=... \
  -e DATADOG_API_KEY=... \
  -e DATADOG_APP_KEY=... \
  -e STATUSGATOR_API_TOKEN=... \
  -e LLM_MODE=haiku \
  coral-beacon
```

---

## Railway (recommended — fastest Python + binary deploy)

1. Push to GitHub (`Nedjagang/coral-beacon` — the main submission repo)
2. New project → "Deploy from GitHub repo" → select `coral-beacon` path
3. Set all 6 env vars in Railway dashboard under Variables
4. Deploy — Railway auto-detects Python via `requirements.txt`

If the Dockerfile is present, Railway uses it. Otherwise Nixpacks will build a Python image (no Coral binary — use Dockerfile).

Railway free tier: 500 hours/month, custom domain via `<name>.railway.app`.

---

## Fly.io (alternative)

```bash
cd coral-beacon
fly launch --name coral-beacon --region sjc --no-deploy
# Set secrets:
fly secrets set ANTHROPIC_API_KEY=sk-ant-... GITHUB_TOKEN=... \
  PAGERDUTY_API_TOKEN=... DATADOG_API_KEY=... \
  DATADOG_APP_KEY=... STATUSGATOR_API_TOKEN=...
fly deploy
```

Fly free tier: 3 shared VMs + 3 GB volumes.

For persistent `data/` across deploys:
```bash
fly volumes create coral_data --size 1  # 1 GB
```
Then mount at `/app/data` in `fly.toml`.

---

## Render (alternative)

1. New Web Service → connect GitHub repo
2. Root directory: `coral-beacon`
3. Build command: `pip install -r requirements.txt`
4. Start command: `./scripts/start.sh`  (see below — needs Coral binary install)
5. Set env vars in Render dashboard

`scripts/start.sh`:
```bash
#!/bin/bash
set -e
# Install Coral if not present
if ! command -v coral &>/dev/null; then
  curl -fsSL https://withcoral.com/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
# Configure Coral sources
CORAL_CONFIG_DIR=/app/coral-config coral source add --file /app/runbook.yaml 2>/dev/null || true
# Start server
uvicorn main:app --host 0.0.0.0 --port "$PORT"
```

---

## Coral config at deploy time

The Coral config at `$CORAL_CONFIG_DIR/config.toml` references env vars by name (not values). The bundled file at `coral-config/config.toml` has all 4 API sources pre-declared — secrets are injected at runtime from env vars.

The `runbook` source must be registered separately:
```bash
CORAL_CONFIG_DIR=/app/coral-config coral source add --file /app/runbook.yaml
```

This is idempotent — safe to run on every container start.

---

## Environment variables reference

| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `GITHUB_TOKEN` | Fine-grained PAT: Contents (read) + Pull Requests (read) for `Nedjagang/coral-beacon-demo` |
| `PAGERDUTY_API_TOKEN` | PagerDuty → Integrations → API Access Keys → Create New API Key |
| `DATADOG_API_KEY` | Datadog → Organization Settings → API Keys |
| `DATADOG_APP_KEY` | Datadog → Organization Settings → Application Keys |
| `STATUSGATOR_API_TOKEN` | StatusGator → Account Settings → API |
| `CORAL_CONFIG_DIR` | Set to `/app/coral-config` in container; `~/coral-hackathon` locally |
| `LLM_MODE` | `haiku` for demo (cheap); `sonnet` for high-quality output |

---

## Health check

```
GET /health  → {"status": "ok"}
```

Railway/Fly/Render can use this for liveness probes.

---

## Data persistence

| Path | Content | Persistence needed? |
|---|---|---|
| `data/runbook.jsonl` | Living Runbook — grows over time | Yes — mount a volume |
| `data/latest_investigation.json` | Last agent result | Ephemeral OK (UI shows stale on restart) |

For the demo recording, ephermal storage is fine — seed the scenario, run the investigation, record the video in one session.

---

## Post-deploy checklist

- [ ] `GET /health` returns 200
- [ ] `GET /api/runbook` returns existing runbook entries
- [ ] `GET /investigate/<id>?mode=mock` returns canned postmortem (verifies routing)
- [ ] `GET /investigate/<id>?mode=haiku` returns real postmortem (verifies Anthropic + Coral)
- [ ] Web UI at `/` shows timeline and runbook table
- [ ] Note the public URL for submission form
