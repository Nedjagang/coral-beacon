# Coral Beacon — Setup on a New Machine

Everything you need to go from a fresh clone to a running investigation.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | `sudo apt install python3.12` or brew |
| git | any | pre-installed |
| gh CLI | any | `brew install gh` / [cli.github.com](https://cli.github.com) |
| Coral CLI | 0.3.0 | `scripts/setup.sh` installs it automatically |

---

## API keys you need

Get these before starting. All have free tiers.

| Key | Where to get it | Used for |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Claude agent |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Fine-grained PATs → New token. Scopes: **Contents** (read) + **Pull Requests** (read) for `Nedjagang/coral-beacon-demo` | GitHub source |
| `PAGERDUTY_API_TOKEN` | PagerDuty → Integrations → API Access Keys → Create New API Key | PagerDuty source |
| `DATADOG_API_KEY` | Datadog → Organization Settings → API Keys | Datadog source |
| `DATADOG_APP_KEY` | Datadog → Organization Settings → Application Keys | Datadog source |
| `STATUSGATOR_API_TOKEN` | StatusGator → Account → API | StatusGator source |

---

## Step 1 — Clone

```bash
git clone https://github.com/Nedjagang/coral-beacon.git
cd coral-beacon
```

---

## Step 2 — Copy .env and fill in keys

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in all six API keys. Leave `LLM_MODE=haiku` and `CORAL_TRANSPORT=subprocess` as-is.

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=github_pat_...
PAGERDUTY_API_TOKEN=...
DATADOG_API_KEY=...
DATADOG_APP_KEY=...
STATUSGATOR_API_TOKEN=...
```

---

## Step 3 — Run setup (one command)

```bash
bash scripts/setup.sh
```

This script:
1. Creates `.venv` and installs Python dependencies
2. Downloads the Coral CLI binary if not already in `PATH`
3. Registers the Living Runbook as a Coral custom source (path-aware)
4. Writes `CORAL_CONFIG_DIR` into your `.env`
5. Runs a smoke test — starts the server, hits `/health`, shuts it down

If the script exits asking you to fill in `.env`, do that then re-run.

---

## Step 4 — Verify Coral sources

```bash
source .venv/bin/activate
set -a && source .env && set +a

coral sql "SELECT DISTINCT schema_name FROM coral.tables ORDER BY 1"
```

Expected output:
```
+-------------+
| schema_name |
+-------------+
| datadog     |
| github      |
| pagerduty   |
| runbook     |
| statusgator |
+-------------+
```

If a schema is missing, re-run `scripts/setup.sh` — it will re-register missing sources.

---

## Step 5 — Start the server

```bash
source .venv/bin/activate
set -a && source .env && set +a
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` — you should see the dark-theme UI.

---

## Step 6 — Seed the demo scenario

In a second terminal:

```bash
source .venv/bin/activate
set -a && source .env && set +a
python scripts/seed_demo.py
```

This creates:
- A merged GitHub PR in `Nedjagang/coral-beacon-demo`
- A `web.error.rate` metric spike in Datadog
- A P1 incident in PagerDuty

Note the PagerDuty incident ID printed at the end.

---

## Step 7 — Run an investigation

```bash
# Free mock (no API cost, tests routing)
curl "http://localhost:8000/investigate/<INCIDENT_ID>?mode=mock"

# Real run with Haiku (~$0.05)
curl "http://localhost:8000/investigate/<INCIDENT_ID>?mode=haiku"

# MCP transport (proves Phase 7 integration)
curl "http://localhost:8000/investigate/<INCIDENT_ID>?mode=haiku&transport=mcp"
```

After the real run, refresh `http://localhost:8000` — the timeline, narrative, and runbook table all populate.

---

## Troubleshooting

**`coral: command not found`**

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this to `~/.bashrc` or `~/.zshrc` permanently.

---

**`KeyError: 'ANTHROPIC_API_KEY'`**

You started the server without loading `.env`. Always do:
```bash
set -a && source .env && set +a
uvicorn main:app --reload --port 8000
```

---

**Seed script fails with git push 403**

The `GITHUB_TOKEN` in `.env` is a read-only fine-grained PAT — that's correct for Coral queries. For the seed script's git operations, authentication goes through the `gh` CLI. Run:

```bash
gh auth login
gh auth setup-git
```

Then re-run `python scripts/seed_demo.py`.

---

**`runbook` schema missing from Coral tables**

Re-run setup:
```bash
set -a && source .env && set +a
bash scripts/setup.sh
```

The setup script re-registers the runbook source with the correct path for your machine.

---

**Web UI shows empty panels**

Run an investigation first (Step 7) — the UI reads `data/latest_investigation.json` which only exists after the first `/investigate` call.

---

## Project structure (quick reference)

```
coral-beacon/
├── main.py                 # FastAPI — start here
├── agent/
│   ├── investigator.py     # Claude tool_use agent loop
│   ├── coral_client.py     # Coral SQL routing (subprocess / MCP)
│   ├── coral_mcp_client.py # MCP stdio transport
│   └── runbook.py          # Writes to Living Runbook
├── queries/                # 5 cross-source SQL files
├── data/runbook.jsonl      # Living Runbook (append-only)
├── static/index.html       # Dark-theme SPA
├── scripts/
│   ├── setup.sh            # First-time setup
│   ├── seed_demo.py        # Demo scenario seeder
│   └── start.sh            # Docker entrypoint
├── coral-config/
│   └── config.toml         # Coral source declarations (no secrets)
├── runbook.yaml            # Coral custom source spec
├── Dockerfile              # Container build
└── docs/
    ├── ARCHITECTURE.md     # Full technical reference
    ├── DEPLOY.md           # Railway / Fly / Render guide
    └── JOURNEY.md          # Coral learning log
```

For a deeper technical picture — how the agent loop works, Coral v0.3.0 quirks, transport details — read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
