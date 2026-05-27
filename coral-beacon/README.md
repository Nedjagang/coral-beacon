# Coral Beacon 🪸

> **AI SRE Investigator** — when a P1 fires at 2am, Coral Beacon correlates PagerDuty, GitHub, Datadog, and StatusGator with cross-source Coral SQL, writes a full root-cause postmortem in under a minute, and saves it to a Living Runbook so the next incident resolves faster.

Submission for the [Pirates of the Coral-bean hackathon](https://www.wemakedevs.org/hackathons/coral/) · May 25–31 2026 · Solo entry by [@Nedjagang](https://github.com/Nedjagang)

---

## What it does

```
Seed scenario (2am page):
  GitHub  → PR "fix: increase connection pool MAX_CONNECTIONS from 10 to 50" merged
  Datadog → web.error.rate climbs 0.01 → 0.14 (30-second window)
  PagerDuty → P1 incident "Web service error rate spike 14%" triggered

Coral Beacon (automatic):
  1. Pulls incident + on-call data from PagerDuty
  2. JOINs the triggering GitHub PR via cross-source Coral SQL
  3. Checks Datadog monitors and StatusGator for third-party correlation
  4. Reads its own Living Runbook (a Coral JSONL source) for past matches
  5. Writes a full incident postmortem in Markdown
  6. Appends the postmortem back to the Living Runbook for next time
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Browser                              │
│          Timeline · Narrative · Runbook table (dark UI)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI  (main.py)                          │
│  GET /investigate/{id}?mode=haiku&transport=subprocess          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│              Claude tool_use agent  (investigator.py)           │
│  Model: claude-haiku-4-5 (default) / claude-sonnet-4-6          │
│  Prompt caching on system prompt + tool definitions             │
│  Up to 30 turns · rate-limit retry with backoff                 │
└──────┬──────────────────────────────────────────────────────────┘
       │ tool calls
┌──────▼──────────────────────────────────────────────────────────┐
│                  coral_client.coral_sql()                       │
│                                                                 │
│  CORAL_TRANSPORT=subprocess (default)     CORAL_TRANSPORT=mcp   │
│  ┌─────────────────────────────┐   ┌───────────────────────┐   │
│  │  coral sql "<stripped_sql>" │   │  coral mcp-stdio      │   │
│  │  subprocess, ASCII table    │   │  JSON-RPC stdio       │   │
│  └─────────────────────────────┘   └───────────────────────┘   │
└──────┬──────────────────────────────────────────────────────────┘
       │ Coral SQL cross-source JOINs
┌──────▼──────────────────────────────────────────────────────────┐
│               Coral CLI v0.3.0  (local process)                 │
│                                                                 │
│  pagerduty.*   github.*   datadog.*   statusgator.*   runbook.* │
│  Live REST API calls — JOINs happen inside Coral, not in Python │
└─────────────────────────────────────────────────────────────────┘
```

### Key Coral SQL queries

| File | What it joins | Why it matters |
|---|---|---|
| `incidents_with_deploys.sql` | `pagerduty.incidents` ⋈ `github.pulls` | Links the P1 to the exact PR that triggered it |
| `datadog_error_spike_correlation.sql` | `pagerduty.incidents` CROSS JOIN `datadog.monitors` | Confirms metric state at incident time |
| `third_party_outage_correlation.sql` | `pagerduty.incidents` CROSS JOIN `statusgator.monitors` | Rules out third-party infrastructure |
| `deployer_vs_oncall.sql` | `pagerduty.oncalls` CROSS JOIN `github.user_repos` | Identifies who deployed vs. who is on-call |
| `full_timeline.sql` | `pagerduty.incidents` UNION ALL `pagerduty.oncalls` | Chronological event stream |

### Living Runbook

The agent's postmortem store is itself a **Coral custom source** (`backend: jsonl`). On every new incident the agent:
1. `SELECT * FROM runbook.entries WHERE service_id = '...'` — finds past matches
2. Writes the new postmortem via `record_runbook_entry` tool → `data/runbook.jsonl`

This means the runbook grows over time and future investigations start with institutional memory already loaded. Coral queries itself.

---

## Run locally

### Prerequisites

- Python 3.12+
- [Coral CLI](https://withcoral.com/docs/getting-started/installation) (`coral` in PATH)
- API keys for: PagerDuty (dev account), GitHub (fine-grained PAT), Datadog, StatusGator, Anthropic

### Setup

```bash
git clone https://github.com/Nedjagang/coral-beacon
cd coral-beacon

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — fill in all 6 API keys
```

### Wire Coral sources

```bash
export CORAL_CONFIG_DIR=~/coral-hackathon
coral source add pagerduty
coral source add github
coral source add datadog
coral source add statusgator
coral source add --file runbook.yaml  # Living Runbook custom source
```

Verify:
```bash
coral sql "SELECT DISTINCT schema_name FROM coral.tables ORDER BY 1"
# Expected: datadog, github, pagerduty, runbook, statusgator
```

### Seed the demo scenario

```bash
python scripts/seed_demo.py
# Outputs: GitHub PR number + Datadog metric + PagerDuty incident ID
```

### Start the server

```bash
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`

### Run an investigation

```bash
# Subprocess transport (default), Haiku model
curl "http://localhost:8000/investigate/Q35GWMTOFW803K?mode=haiku"

# MCP transport, Sonnet model
curl "http://localhost:8000/investigate/Q35GWMTOFW803K?mode=sonnet&transport=mcp"

# Free mock (no API call)
curl "http://localhost:8000/investigate/Q35GWMTOFW803K?mode=mock"
```

---

## Transports

Coral Beacon supports two transports for all Coral SQL execution. Toggle with the `CORAL_TRANSPORT` environment variable or the `?transport=` query parameter.

### Subprocess (default)

```
CORAL_TRANSPORT=subprocess   # or omit — this is the default
```

- Invokes `coral sql "<query>"` as a subprocess per call.
- Returns ASCII table output.
- Most stable; used for all validated queries.

### MCP (stdio)

```
CORAL_TRANSPORT=mcp
```

- Spawns `coral mcp-stdio` and speaks MCP JSON-RPC over stdin/stdout.
- Returns `{"rows": [...]}` JSON — cleaner for LLM processing.
- Each `coral_sql()` call creates a fresh MCP session (initialize → call → close).
- Evidence: `docs/evidence/phase7/mcp_transport_transcript.json`

---

## Cost

| Mode | Model | Avg cost/investigation | Avg turns |
|---|---|---|---|
| `mock` | none | $0.00 | 0 |
| `haiku` | claude-haiku-4-5 | ~$0.05 | 7 |
| `sonnet` | claude-sonnet-4-6 | ~$0.20 | 5–8 |

Prompt caching reduces repeat-investigation cost by ~90% (system + tool definitions cached).

---

## Project structure

```
coral-beacon/
├── main.py                    # FastAPI — routes, static mount
├── requirements.txt
├── runbook.yaml               # Coral custom source spec
├── agent/
│   ├── coral_client.py        # coral_sql() with transport routing
│   ├── coral_mcp_client.py    # MCP stdio transport
│   ├── investigator.py        # Claude tool_use agent
│   └── runbook.py             # append_runbook_entry()
├── queries/                   # 6 Coral SQL files
├── data/
│   ├── runbook.jsonl          # Living Runbook (append-only)
│   └── latest_investigation.json
├── static/index.html          # Dark-theme SPA
├── scripts/seed_demo.py       # Idempotent demo seeder
└── docs/
    ├── PRD.md
    ├── PLAN.md
    ├── ARCHITECTURE.md        # Full technical reference
    └── JOURNEY.md             # Coral learning log
```

---

## Hackathon criterion coverage

| Criterion | Evidence |
|---|---|
| **Best Use of Coral** | 5 cross-source JOINs; custom JSONL source connector; prompt caching; MCP integration mode; `coral.tables` schema discovery in system prompt |
| **Technical Implementation** | Claude `tool_use` agentic loop; prompt caching; rate-limit retry; dual transport (subprocess + MCP); FastAPI + vanilla SPA |
| **Creativity & Originality** | Living Runbook: the agent registers its own postmortem store as a Coral source and queries it on the next incident — Coral querying Coral |
| **Potential Impact** | Any on-call team with PagerDuty + GitHub + Datadog can cut mean time to hypothesis from 15 min to <1 min |
| **Aesthetics & UX** | Dark-theme timeline SPA; source color-coded events; incident → deploy → metric → outage as one visual story |
| **Learning & Growth** | `docs/JOURNEY.md` — daily Coral learnings from a first-time user; all quirks and workarounds documented |

---

## License

MIT
