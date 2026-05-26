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
