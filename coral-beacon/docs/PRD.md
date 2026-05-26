# Coral Beacon — Product Requirements Document

> Owner: Praneeth · Hackathon: Pirates of the Coral-bean (May 25–31, 2026) · Track: Enterprise Agent

## 1. Vision (one sentence)

A self-improving AI SRE that, the moment a high-urgency incident fires, runs cross-source Coral SQL across PagerDuty, GitHub, Datadog, and StatusGator — and a runbook it built itself — to produce a full root-cause narrative before the on-call has finished pouring coffee.

## 2. The problem

When a P1 fires at 2am, the on-call engineer spends 5–15 minutes context-switching across PagerDuty, GitHub, Datadog, and third-party status pages just to *form a hypothesis*. Half the time the answer is staring back from a postmortem written six months ago that nobody can find. We collapse that loop to seconds.

## 3. Why this wins (criterion-by-criterion)

| Criterion | How we earn it |
| --- | --- |
| 🏴 Potential Impact | Every company with on-call engineers needs this. Demoable revenue-loss math via Incident Cost Calculator. |
| ⚓ Creativity & Originality | The Living Runbook — agent registers its own postmortem store as a Coral source, then queries itself on the next incident. Coral × Coral. |
| 🗺️ Learning & Growth | `docs/JOURNEY.md` captures every "what I learned about Coral today" note from a first-time user — judges reward this explicitly. |
| ⚔️ Technical Implementation | Claude tool_use agent autonomously chains 5+ cross-source queries. Prompt caching. MCP transport alternative. |
| 🎨 Aesthetics & UX | Web UI timeline that shows incident → deploy → metric spike → outage as one visual story. |
| 🪸 Best Use of Coral | Cross-source JOINs (no Python stitching), custom source connector, caching, schema discovery via `coral.tables`, and MCP integration mode. |

## 4. Hackathon-rule alignment (verified from /rules and /resources)

- ✅ **New project, all code created during the event.** First commit is `e04805a 2026-05-25 16:37 IST` — inside the May 25 start. No pre-existing code is being modified. Plan-only discussion before May 25 is permitted.
- ⚠️ **Must star github.com/withcoral/coral and join the Coral Discord** — required for prize eligibility. Phase 0 task.
- ✅ **Solo or team of 1–4.** Solo entry assumed unless Praneeth recruits a crew.
- ✅ **IP retained by team.** No assignment to sponsors.
- ✅ **Submission format:** GitHub link + deployed URL + YouTube demo ≤3 min. All three planned in Phase 8.
- ✅ **Allowed:** third-party tools, frameworks, OSS libraries, public APIs, public assets. Anthropic SDK, FastAPI, Coral CLI, all four data-source APIs — all permitted.
- ✅ **Coral feature coverage that improves judging:** SQL interface, cross-source joins, schema learning, caching, MCP integration. Every one of these is in scope below.

## 5. Scope — in (MVP for submission)

1. FastAPI service with `/investigate/{incident_id}` endpoint.
2. Claude tool_use agent (Anthropic SDK, Sonnet 4.6, prompt caching) that calls Coral.
3. Four sources wired: PagerDuty, GitHub, Datadog, StatusGator.
4. Five named cross-source SQL queries, every one a real multi-schema JOIN.
5. Living Runbook custom Coral source (write-back + queryable).
6. Web UI: timeline view + agent narrative + similar-past-incident panel.
7. Demo seed scripts for a reproducible 2am-incident scenario.
8. MCP transport option (Coral exposed to Claude as an MCP server).
9. Public deployment + 3-min YouTube demo + submission.

## 6. Scope — out (don't get tempted)

- GitHub Action for pre-deploy blast radius (cool but separate distribution surface; Phase 9+ stretch).
- Multi-tenant auth, RBAC, SSO.
- Real production data — demo runs on seeded data only.
- Mobile app.
- Slack / Teams bot.
- Any of the additional 7 "crazy features" from the brainstorm beyond what's in Scope-in.

## 7. Non-functional requirements

- **Determinism for demo:** the same seed script always produces the same agent narrative ordering. Record the demo once, ship it.
- **Cold-start to first agent token:** ≤10 seconds on the deployed instance.
- **Prompt caching enabled:** system prompt + tool definitions cached so repeat investigations are fast and cheap.
- **No secrets in repo.** `.env` is gitignored; deployment uses platform secret manager.
- **README + JOURNEY are presentation-grade** — judges read these.

## 8. Success criteria

The submission wins if, by 23:59 May 31 local: (a) all 9 in-scope items shipped, (b) demo video reproducibly shows the agent producing a useful postmortem in under 60s, (c) at least one query in the demo references the runbook source so the meta-loop is visible, and (d) the deployed link works on a fresh browser tab.
