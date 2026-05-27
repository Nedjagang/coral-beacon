# Coral Beacon — Architecture Reference

> This document is the single source of truth for any Claude session working on this codebase.
> Read this before touching any file. Supplements `PLAN.md` (what to build) and `PRD.md` (why).

---

## Directory layout

```
coral-beacon/
├── main.py                    # FastAPI app — routes + static file mount
├── requirements.txt           # anthropic, fastapi, uvicorn, httpx, aiofiles
├── runbook.yaml               # Coral custom source spec for the Living Runbook
│
├── agent/
│   ├── coral_client.py        # coral_sql() — routes subprocess ↔ MCP via CORAL_TRANSPORT
│   ├── coral_mcp_client.py    # MCP transport: spawns `coral mcp-stdio`, JSON-RPC stdio
│   ├── investigator.py        # Claude tool_use agent loop + SYSTEM_PROMPT + TOOLS list
│   └── runbook.py             # append_runbook_entry() — writes to data/runbook.jsonl
│
├── queries/                   # All Coral SQL files — every one is a cross-source JOIN
│   ├── incidents_with_deploys.sql          # PD incidents ⋈ github.pulls
│   ├── datadog_error_spike_correlation.sql # PD incidents CROSS JOIN datadog.monitors
│   ├── third_party_outage_correlation.sql  # PD incidents CROSS JOIN statusgator.monitors
│   ├── deployer_vs_oncall.sql              # PD oncalls CROSS JOIN github.user_repos
│   ├── full_timeline.sql                   # PD incidents UNION ALL PD oncalls (same-schema)
│   └── list_tables.sql                     # coral.tables discovery query
│
├── data/
│   ├── runbook.jsonl              # Living Runbook — append-only, also a Coral source
│   └── latest_investigation.json # Last agent result persisted by /investigate endpoint
│
├── static/
│   └── index.html             # Vanilla JS SPA — dark theme, timeline + narrative + runbook
│
├── scripts/
│   └── seed_demo.py           # Creates GitHub PR + Datadog spike + PagerDuty incident
│
└── docs/
    ├── PRD.md                 # What we're building and why (judging-criterion mapping)
    ├── PLAN.md                # Phased build plan — the SOP, phases 0–8
    ├── ARCHITECTURE.md        # This file
    ├── JOURNEY.md             # Daily Coral learnings (Learning & Growth criterion)
    └── evidence/
        ├── phase6/            # seed_demo.py output + incidents_with_deploys result
        └── phase7/            # MCP transport transcript
```

---

## Request flow

```
Browser / curl
      │
      ▼
FastAPI (main.py)
  GET  /                         → serves static/index.html
  GET  /api/latest               → reads data/latest_investigation.json
  GET  /api/runbook              → coral_sql(SELECT … FROM runbook.entries) → JSON
  GET  /investigate/{id}?mode=&transport=
      │
      ▼
agent/investigator.py
  investigate(incident_id, mode)
      │
      ├─ LLM_MODE=mock  → canned postmortem, 0 API calls
      │
      └─ LLM_MODE=haiku/sonnet
           │
           ▼
         Anthropic Messages API (tool_use loop, max 30 turns)
           │  system: SYSTEM_PROMPT (cached)
           │  tools:  TOOLS list (cached via cache_control on last tool)
           │
           ├─ coral_query(sql)       → agent/coral_client.coral_sql()
           ├─ coral_list_tables()    → coral_sql("SELECT … FROM coral.tables …")
           ├─ coral_describe_table() → coral_sql("SELECT … FROM coral.columns …")
           ├─ query_runbook(sql)     → coral_sql(sql)   [runbook.entries]
           └─ record_runbook_entry() → agent/runbook.append_runbook_entry()
                                           └─ appends JSON line to data/runbook.jsonl
```

---

## Coral transports

`coral_client.coral_sql(sql)` checks `CORAL_TRANSPORT` env var:

| `CORAL_TRANSPORT` | Implementation | Output format |
|---|---|---|
| `subprocess` (default) | `coral sql <stripped_sql>` subprocess | ASCII table string |
| `mcp` | `coral mcp-stdio` JSON-RPC stdio session | JSON `{"rows": [...]}` string |

The MCP client (`coral_mcp_client.py`) lifecycle per call:
1. Spawn `coral mcp-stdio`
2. Send `initialize` request → receive capabilities
3. Send `notifications/initialized`
4. Send `tools/call` with `name: "sql"` → receive JSON rows
5. Close stdin, wait for process exit

`/investigate/{id}?transport=mcp` sets `CORAL_TRANSPORT=mcp` in `os.environ` for that request.

**Important:** `GITHUB_TOKEN` must be stripped from the subprocess env for any `git` operations (see `seed_demo.py`). The fine-grained PAT stored as `GITHUB_TOKEN` is read-only; git pushes require the full `gh` CLI token stored in `~/.config/gh/hosts.yml`.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `GITHUB_TOKEN` | Yes | Fine-grained PAT (read-only: Contents + PRs) |
| `PAGERDUTY_API_TOKEN` | Yes | PagerDuty REST API v2 key |
| `DATADOG_API_KEY` | Yes | Datadog API key |
| `DATADOG_APP_KEY` | Yes | Datadog Application key |
| `STATUSGATOR_API_TOKEN` | Yes | StatusGator API token |
| `CORAL_CONFIG_DIR` | Yes | Path to coral config dir (default: `~/coral-hackathon`) |
| `LLM_MODE` | No | `mock` \| `haiku` \| `sonnet` (default: `haiku`) |
| `CORAL_TRANSPORT` | No | `subprocess` \| `mcp` (default: `subprocess`) |

---

## Coral source configuration

Coral sources live in `$CORAL_CONFIG_DIR/config.toml`. The bundled sources (github, pagerduty, datadog, statusgator) pull secrets from env vars by name. The `runbook` source is a custom JSONL source registered via `coral source add --file runbook.yaml`.

`runbook.yaml` spec:
- `backend: jsonl`
- `tables[0].source.location: file:///absolute/path/to/data/`
- `tables[0].source.glob: "runbook.jsonl"`
- Columns: `id, created_at, service, service_id, summary, root_cause, resolution_steps, resolution_minutes, fingerprint`

**Coral v0.3.0 known constraints (do not work around in Python):**
1. `github.pulls` requires constant `WHERE owner='…' AND repo='…'` — no variable join keys.
2. UNION ALL across different schemas fails with Arrow buffer bug. Use same-schema UNION ALL only.
3. `pagerduty.incidents.created_at` is `Utf8` — use `CAST(created_at AS TIMESTAMP)` for date math.
4. `coral sql` treats lines starting with `--` as CLI flags. Strip SQL comment lines before subprocess call.

---

## Agent design

**System prompt strategy:** Pre-loads all 5 schema definitions inline so Haiku doesn't need exploration turns. Reduces average turn count from 20+ to 7.

**Prompt caching:** `cache_control: {"type": "ephemeral"}` on the last tool (`record_runbook_entry`) covers the full tool list AND the system prompt (Anthropic caches everything before the last cache_control point). Cache creation ~$0.0015; cache read ~$0.00015 per subsequent run.

**Turn cap:** 30 turns. Haiku typically uses 7; Sonnet uses 5–8.

**Rate limit handling:** 4 attempts with backoff `60 * (attempt+1)` seconds. The $5 Anthropic free tier limits 30K input tokens/minute.

**Mock mode:** Returns `_MOCK_POSTMORTEM` instantly with `{incident_id}` substituted. Use for UI wiring and tests.

---

## Web UI

`static/index.html` — single file, no build step, no framework.

- **Layout:** two-panel grid (left: timeline, right: narrative) + bottom runbook table.
- **CSS vars:** `--bg: #0d1117`, `--coral: #f0734a`, dark theme throughout.
- **Source color coding:** 🔴 PD · 📊 DD · 🌐 SG · 🟢 GH · 📖 RB
- **Data flow:** on load → `GET /api/latest` (timeline + narrative) + `GET /api/runbook` (runbook table). Runbook auto-refreshes every 30s.
- **Markdown rendering:** inline JS converts `##` headings, `**bold**`, `` `code` ``, tables, and lists to HTML.

---

## Demo seed script

`scripts/seed_demo.py` creates a reproducible incident timeline:

1. **GitHub** — checks for merged PR `fix/connection-pool-timeout` in `Nedjagang/coral-beacon-demo`; if absent, clones repo, creates branch + commit, pushes, opens PR, merges.
2. **Datadog** — POSTs 6 gauge points of `web.error.rate` climbing 0.01 → 0.14 to `https://api.us5.datadoghq.com/api/v1/series`.
3. **PagerDuty** — creates a P1 incident on service `P017TQH` titled "Web service error rate spike 14% — deploy PR #N".

Run: `python scripts/seed_demo.py [--reset]`

`--reset` resolves any open PD incidents first, then re-seeds.

The script is **idempotent**: re-running detects existing merged PR and skips GitHub; always re-submits Datadog metrics and creates a new PD incident (intentional — each run produces a fresh incident ID to investigate).

**Auth note:** The script strips `GITHUB_TOKEN` from the subprocess environment before any `git` command. All `gh` CLI operations (`gh pr create`, `gh pr merge --yes`) use the ambient gh token.

---

## Phase status

| Phase | Status | Key artifact |
|---|---|---|
| 0 — Compliance | ✅ | Discord joined, repo starred |
| 1 — Coral sources | ✅ | 4 sources live (github, pagerduty, datadog, statusgator) + runbook |
| 2 — Agent loop | ✅ | `agent/investigator.py` — tool_use, caching, rate-limit retry |
| 3 — 5 SQL queries | ✅ | `queries/` — all 5 files validated against seeded data |
| 4 — Living Runbook | ✅ | `runbook.yaml` custom source + `agent/runbook.py` write-back |
| 5 — Web UI | ✅ | `static/index.html` — dark theme SPA, timeline + narrative |
| 6 — Seed script | ✅ | `scripts/seed_demo.py` — GitHub + Datadog + PagerDuty |
| 7 — MCP transport | ✅ | `agent/coral_mcp_client.py` + `CORAL_TRANSPORT=mcp` routing |
| 8 — Deploy + submit | 🔄 | Dockerfile, Railway deploy, README polish, YouTube demo |

---

## Known issues / gotchas for Phase 8

1. **Coral binary must be in `PATH` at deploy time.** Download from GitHub releases for `x86_64-unknown-linux-gnu`.
2. **`CORAL_CONFIG_DIR` must point to a directory with `config.toml` and the runbook source registered.** Either bundle a pre-configured `config.toml` or run `coral source add` at container startup.
3. **`runbook.jsonl` must be writable at runtime** — the agent appends to it. Mount as a volume or accept data loss on container restart.
4. **`data/latest_investigation.json` is also written at runtime** — same persistence concern.
5. **MCP transport spawns a new `coral mcp-stdio` process per SQL call** — acceptable for demo throughput; not suitable for high concurrency.
