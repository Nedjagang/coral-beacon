# Coral Beacon — Claude instructions

This repo is a hackathon entry. The plan is fixed and lives in `coral-beacon/docs/`:

- **`coral-beacon/docs/PRD.md`** — what we're building and why.
- **`coral-beacon/docs/PLAN.md`** — phased build plan (the SOP). Source of truth.
- **`coral-beacon/docs/JOURNEY.md`** — daily learning log (Learning & Growth criterion).

## Rules every Claude session must follow

1. **Read `docs/PLAN.md` before suggesting anything.** Match work to the active phase. If the user asks for something out-of-phase, say so and ask to update the plan first.
2. **No scope creep.** Items under "Scope — out" in the PRD stay out unless the user explicitly overrides.
3. **Hackathon rule constraints** (from <https://www.wemakedevs.org/hackathons/coral/rules>):
   - New project only — all code must originate inside this repo, committed during May 25–31 2026.
   - Submission = GitHub link + deployed URL + YouTube demo ≤3 min.
   - Solo or team of ≤4.
   - Team must have starred withcoral/coral and joined the Coral Discord.
4. **Best Use of Coral = the scoring axis.** Cross-source JOINs in SQL, custom source connector for the runbook, caching, MCP integration. Never stitch sources in Python when a Coral JOIN can do it.
5. **Secrets:** `.env` is gitignored. Never echo or commit API keys. Never push without confirming.
6. **Phase end-of-day:** suggest an entry for `docs/JOURNEY.md` capturing what was learned about Coral specifically — that's our Learning & Growth evidence.

## Tech stack

- Python 3.14 (venv at `coral-beacon/.venv`)
- FastAPI + uvicorn (already in `requirements.txt`)
- Anthropic SDK with tool_use, prompt caching, model `claude-sonnet-4-6` (or `claude-opus-4-7` if explicitly requested)
- Coral CLI via subprocess (`agent/coral_client.py`) and, in Phase 7, via MCP
- Vanilla HTML/CSS/JS for the UI (no framework)

## Conventions

- One PR per phase. Commits squashed.
- Every new query lives as a file under `coral-beacon/queries/`, with a header comment naming the schemas it joins.
- Every new agent tool gets a one-line docstring used verbatim in the LLM tool description.
- Evidence (transcripts, screenshots) goes under `coral-beacon/docs/evidence/phaseN/`.

## When suggesting Claude Code skills

The plan in `docs/PLAN.md` already maps skills to phases. Don't suggest skills outside that map unless there's a clear reason — extra skill invocations cost time the hackathon doesn't have.
