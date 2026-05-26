# Coral Beacon — Cohort-Style Build Plan (SOP)

> Today is **2026-05-26 (Day 2)**. Submission deadline **2026-05-31 23:59 local**. 6 calendar days remain (one is the submission day itself).
>
> This document is the source of truth. If reality diverges from this plan, **update this file first**, then change code. Every phase ends with a definition-of-done (DoD) that must be ticked before the next phase begins.

## Operating rules (stick to these)

1. **No phase skips.** Phases are ordered for a reason — each one's DoD unblocks the next.
2. **One PR per phase.** Small, focused, reviewable. Squash-merge to `master`.
3. **Every phase ends with `./scripts/run_coral_query.sh` proving the new capability** (or, for UI/demo phases, a screenshot in `docs/evidence/`).
4. **End-of-day update** to `docs/JOURNEY.md` — this is what we cite for the *Learning & Growth* criterion.
5. **Never push secrets.** `.env`, API keys, recorded session tokens stay local.
6. **Out-of-scope ideas go to `docs/STRETCH.md`**, not into the current sprint.

## Claude Code skills we will use (and when)

| Skill | When | Why |
| --- | --- | --- |
| `/claude-api` | Building the agent in Phase 2 | Caching, tool_use, model-specific patterns straight from the SDK skill |
| `/run` | After each phase | Launch the FastAPI app and the agent so we're testing real behavior, not just unit checks |
| `/verify` | Phases 2, 5, 8 | Confirm the agent loop, the UI, and the deployed instance actually work end-to-end |
| `/code-review` | End of Phase 5 and Phase 7 | High-effort review of the agent + MCP code before the demo |
| `/security-review` | Day before submission | Catch any leaked keys, unsafe subprocess args, or XSS in the UI |
| `/init` | Already replaced by hand-written `CLAUDE.md` in repo root | Project-specific instructions for any future Claude session |
| `/fewer-permission-prompts` | Once, early | Cuts friction during the rest of the sprint |
| `/loop` | Optional, Phase 8 | Periodic "is the deployed instance still up?" check during demo recording |

## Phase 0 — Compliance & foundations (Mon May 26 morning, 30 min)

**Goal:** legally able to win.

- [ ] Star <https://github.com/withcoral/coral>.
- [ ] Join Coral Discord, post in `#hackathon-general` with team name "Coral Beacon".
- [ ] Register team on wemakedevs.org (solo OK).
- [ ] Generate API keys: GitHub PAT, PagerDuty dev key, Datadog API + APP keys, StatusGator API key. Drop into `.env` (gitignored).
- [ ] Run `/fewer-permission-prompts` so the rest of the sprint has fewer interruptions.

**DoD:** screenshot of starred repo + Discord join + entries in `.env`. Push the screenshots to `docs/evidence/phase0/` (no keys).

## Phase 1 — Coral CLI + 4 sources live (Mon May 26 afternoon)

**Goal:** `coral sql 'SELECT schema_name, table_name FROM coral.tables ORDER BY 1,2'` returns rows from `github`, `pagerduty`, `datadog`, `statusgator`.

- [ ] Install Coral CLI in WSL: `curl -fsSL https://withcoral.com/install.sh | sh`.
- [ ] `coral source add github` — paste PAT.
- [ ] `coral source add pagerduty` — paste dev key.
- [ ] `coral source add datadog` — paste API + APP keys.
- [ ] `coral source add statusgator` — paste API key.
- [ ] Seed PagerDuty dev account: clone `PagerDuty-Samples/pd-populate-dev-account`, `terraform apply`.
- [ ] Run discovery query, capture output to `docs/evidence/phase1/tables.txt`.

**DoD:** `tables.txt` shows ≥1 table per schema; `./scripts/run_coral_query.sh queries/list_tables.sql` succeeds.

## Phase 2 — Claude tool_use agent loop (Tue May 27)

**Goal:** POST `/investigate/{incident_id}` returns a narrative postmortem string after the agent chose, on its own, to call 3+ Coral tools.

- [ ] `Skill(claude-api)` before writing the agent.
- [ ] Create `agent/investigator.py`: Anthropic client, system prompt that defines the SRE persona, prompt caching on system + tool list.
- [ ] Tools: `coral_query(sql)`, `coral_list_tables()`, `coral_describe_table(schema, name)`. Keep small — let the LLM compose SQL.
- [ ] Replace `/investigate/deploys` with `/investigate/{incident_id}` in `main.py`.
- [ ] Use `claude-sonnet-4-6` (or `claude-opus-4-7` if budget allows — Sonnet is plenty).
- [ ] `/run` and `/verify` against a known seeded incident.

**DoD:** one end-to-end run logged to `docs/evidence/phase2/transcript.txt` showing the model emitting at least one `tool_use` block, receiving Coral output, and producing a final narrative.

## Phase 3 — Five killer cross-source queries (Wed May 28 morning)

**Goal:** five SQL files in `queries/` that each JOIN at least two schemas, all validated against seeded data.

- [ ] `queries/incidents_with_deploys.sql` — already exists, validate it.
- [ ] `queries/third_party_outage_correlation.sql` — PagerDuty ⋈ StatusGator.
- [ ] `queries/datadog_error_spike_correlation.sql` — PagerDuty ⋈ Datadog metrics.
- [ ] `queries/deployer_vs_oncall.sql` — PagerDuty oncalls ⋈ GitHub PRs.
- [ ] `queries/full_timeline.sql` — UNION ALL across PD/GH/SG ordered by timestamp.
- [ ] Each gets a docstring at the top explaining the join key and the expected output shape.
- [ ] Wire each as a high-level tool in the agent so the model can pick a named query.

**DoD:** all 5 queries succeed against the seeded dev data; outputs saved under `docs/evidence/phase3/`.

## Phase 4 — Living Runbook custom Coral source (Wed May 28 afternoon → Thu May 29 morning)

**Goal:** runbook entries are written by the agent post-resolution and queried by the agent on the next incident — via Coral SQL.

- [ ] Read <https://withcoral.com/docs/guides/write-a-custom-source> carefully.
- [ ] Build a minimal Coral source connector that reads `data/runbook.jsonl`.
- [ ] Register the source with `coral source add --file …` (or whatever the docs spec).
- [ ] Schema: `id`, `created_at`, `service`, `summary`, `root_cause`, `resolution_steps`, `resolution_minutes`, `fingerprint` (JSON).
- [ ] Add agent tool `record_runbook_entry(...)` that appends a JSONL line.
- [ ] Add agent tool `query_runbook(sql)` so the agent uses `SELECT … FROM runbook.entries WHERE …`.
- [ ] Inject one or two seed entries so even the first demo run finds a match.

**DoD:** demo: trigger a fresh incident → agent reads existing runbook entry → agent updates the entry with the new resolution → next investigation finds two entries. Transcript in `docs/evidence/phase4/`.

## Phase 5 — Web UI timeline (Thu May 29 afternoon)

**Goal:** opening the deployed URL shows the latest investigation as a beautiful single page.

- [ ] FastAPI serves `static/index.html` at `/`.
- [ ] Vanilla HTML + small JS fetches `/investigate/latest` and renders: incident header, vertical timeline (one row per source event), agent narrative, "Similar past incidents" panel from runbook.
- [ ] Minimal CSS — dark theme, monospace headings, clean line. No framework.
- [ ] `/verify` it in a real browser.

**DoD:** screenshot in `docs/evidence/phase5/timeline.png`. Visually presentable.

## Phase 6 — Demo seed scripts (Fri May 30 morning)

**Goal:** one command produces the demo scenario from a clean state.

- [ ] `scripts/seed_demo.py`:
  1. Create a real PR on a sacrificial demo repo, merge it.
  2. Submit a Datadog `error.rate` series climbing to 0.14 over ~2 minutes.
  3. Trigger a PagerDuty P1 incident on the demo service.
  4. (Optional) Annotate a StatusGator outage if the free tier permits writes; otherwise rely on a real Stripe blip captured in advance.
- [ ] Idempotent — re-runs reset state cleanly.

**DoD:** one shell command produces a runnable scenario, agent investigates it within 60 seconds end-to-end.

## Phase 7 — MCP integration (Fri May 30 afternoon)

**Goal:** Claude can hit Coral via MCP, not just subprocess. Score the MCP-integration axis.

- [ ] Run Coral in MCP server mode (per Coral docs).
- [ ] Add an `--transport mcp` flag to the agent that swaps `coral_query` to call the MCP server.
- [ ] Keep subprocess as the default for stability; document both transports in README.

**DoD:** README section "Transports" with both modes documented; one transcript per mode under `docs/evidence/phase7/`.

## Phase 8 — Deploy, record, submit (Sat May 31)

**Goal:** ship.

- [ ] Deploy to Railway / Fly.io / Render. Pick whichever ships fastest with a Python app + a Coral binary.
- [ ] `/security-review` the diff.
- [ ] `/code-review` the agent + MCP code with effort=high.
- [ ] Polish `README.md`: 30-second pitch, architecture diagram (ASCII is fine), how to run locally, what to look at in the demo.
- [ ] Finalize `docs/JOURNEY.md` (Learning & Growth payload).
- [ ] Record YouTube demo — script below, ≤3 minutes, single take if possible.
- [ ] Submit via wemakedevs form: GitHub URL + deployed URL + YouTube URL.

## Demo video script (≤180 seconds)

| Time | Beat |
| --- | --- |
| 0:00–0:15 | "On-call gets a 2am page. Here's what they normally do" — 3-tab screen recording, chaos. |
| 0:15–0:30 | "Coral Beacon does it in one query language." Show `coral sql` listing all 4 schemas. |
| 0:30–1:00 | Run `python scripts/seed_demo.py`. Show the agent transcript scrolling tool_use calls. |
| 1:00–1:45 | Cut to the Web UI timeline. Walk through PR → metric spike → incident → outage → runbook match. |
| 1:45–2:15 | Highlight: "The agent just queried its own runbook — a Coral source it wrote itself." |
| 2:15–2:45 | Show MCP transport mode running the same investigation. |
| 2:45–3:00 | URL card + "Coral Beacon. Star us." |
