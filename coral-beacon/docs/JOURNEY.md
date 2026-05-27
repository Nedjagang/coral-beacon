# Learning Journey — Coral Beacon

> First-time Coral user log. This is the Learning & Growth criterion's evidence. End each work session with an entry.

## 2026-05-26 — Day 2: Strategy locked, scaffold inherited

**What I knew before today:** Coral is "SQL over APIs." That was about the depth of it.

**What clicked today:**

- Coral is not a database wrapper. The schemas (`github`, `pagerduty`, `datadog`) *are* the services. Each "table" is a live endpoint. JOINs literally happen across HTTP boundaries inside Coral.
- The judging criterion "Best Use of Coral" calls out *cross-source joins* specifically — if I JOIN in Python instead of in SQL, I lose this axis. SQL discipline matters.
- Coral can deploy as an MCP server. That means the Claude agent doesn't have to shell out — it can speak MCP to Coral. This is its own scoring lane on the judging rubric ("MCP integration").
- Custom sources are first-class: <https://withcoral.com/docs/guides/write-a-custom-source>. The Living Runbook idea works because *my own JSONL file can become a Coral source*, which means the agent literally queries itself.
- Free tiers on PagerDuty (permanent dev account), Datadog (14-day trial), and StatusGator (API now on free) plus PagerDuty's `pd-populate-dev-account` Terraform mean I can build a realistic demo without a corporate account.
- Hackathon rules confirm pre-event *planning* is allowed but coding must start May 25. First commit timestamps are inside the window — compliant.

**Decisions made:**

- Scope frozen to 9 in-scope items (see PRD §5). Seven "crazy features" parked in STRETCH.md.
- Demo runs on deterministic seeded data, not live production.
- Subprocess transport stays primary; MCP transport ships as the second mode for scoring.

**Open questions:**

- Does the StatusGator free-tier API support write/annotation endpoints, or only reads? (Affects Phase 6.)
- What's the simplest deployment target that runs both FastAPI *and* a Coral binary? (Railway buildpacks vs Fly machines.)

**Tomorrow (Day 3):** Phase 1 — install Coral, wire 4 sources, prove discovery query. Then immediately begin Phase 2.

## 2026-05-27 — Day 3: Phases 2–7 complete, demo pipeline live

**What I learned about Coral today:**

- **Custom source `backend` must be `jsonl`, not `file`.** The YAML spec has `backend: jsonl` for JSONL files; `backend: file` is invalid. The Living Runbook custom source registers and queries fine once this is corrected.
- **Coral CLI parses `--` as a flag prefix.** Any SQL string starting with a `--` comment line causes `coral sql` to throw a parse error. Fix: strip comment lines before passing SQL to the subprocess. Same issue doesn't exist in the MCP transport (JSON field, not CLI arg).
- **`github.pulls` requires constant `owner` + `repo` filters.** Cross-source JOIN with `pagerduty.incidents` works only after seeding a real repo (`Nedjagang/coral-beacon-demo`) so the constants can be embedded. Zero rows before that; live cross-source join after.
- **UNION ALL across different schemas hits an Arrow buffer bug in v0.3.0.** Workaround: `full_timeline.sql` uses same-source UNION ALL (both tables from `pagerduty`). The cross-source JOINs (CROSS JOIN with `datadog`, `statusgator`, `github`) all work correctly.
- **MCP transport (`coral mcp-stdio`) returns JSON rows, not ASCII tables.** The subprocess transport returns an ASCII table; the MCP endpoint returns `{"rows": [...]}` JSON. Both are useful for Claude — JSON is actually cleaner for the LLM. `coral.tables` metadata returns fewer schemas than the subprocess, but direct table queries (e.g. `pagerduty.incidents`) work fine over MCP.
- **`GITHUB_TOKEN` env var shadows the gh credential helper for git pushes.** When `.env` sets `GITHUB_TOKEN` to a read-only fine-grained PAT, `gh auth git-credential` returns that PAT for git push — which is rejected. Fix: strip `GITHUB_TOKEN` from the subprocess env for all git operations so the stored gh CLI token (`gho_***`) is used.

**What surprised me:**
- The PagerDuty → GitHub cross-source JOIN (`incidents_with_deploys.sql`) confirmed that Coral does the HTTP fanout transparently: one SQL statement, two live API calls, one joined result. No Python glue needed.
- Prompt caching on the tool list works very well — Haiku went from 20+ exploration turns to 7 after I pre-loaded schema info in the system prompt.

**Phases completed today:** 2 (agent loop), 3 (5 cross-source queries), 4 (Living Runbook), 5 (Web UI), 6 (seed script), 7 (MCP transport).

**Tomorrow (Day 4):** Phase 8 — deploy to Railway/Fly, security review, polish README, record demo, submit.
