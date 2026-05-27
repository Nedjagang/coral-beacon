"""Phase 4 — Claude tool_use agent with Living Runbook: reads past incidents from runbook.entries, writes new ones."""

import json
import os
import time
from typing import Any

import anthropic
from dotenv import load_dotenv

from agent.coral_client import coral_sql
from agent.runbook import append_runbook_entry

load_dotenv()

# LLM_MODE controls which backend is used:
#   "mock"   — instant canned response, zero API calls (local dev / UI wiring)
#   "haiku"  — claude-haiku-4-5, cheapest real model (~$0.05/run)
#   "sonnet" — claude-sonnet-4-6, default for demos and submission (default)
LLM_MODE = os.getenv("LLM_MODE", "haiku")

_MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
}

SYSTEM_PROMPT = """You are Coral Beacon, an expert Site Reliability Engineer AI.

Investigate the given PagerDuty incident by running Coral SQL queries, then write a postmortem.

## Available Coral schemas and key tables

pagerduty:
  incidents  — id, title, status, urgency, created_at, service__id, service__name
  oncalls    — user__id, user__summary, escalation_level, escalation_policy__summary, start, end
  log_entries — id, type, summary, created_at, incident__id, agent__summary

datadog:
  monitors   — id, name, type, status, query, tags, created, modified

statusgator:
  boards     — id, name  (use board_id = 'g1t0HJdmfr' for all statusgator table filters)
  monitors   — board_id, id, display_name, monitor_type, filtered_status, unfiltered_status
  incidents  — board_id, id, name, phase, severity, started_at, resolved_at

github:
  pulls      — owner, repo, number, title, merged_at, user__login, state, html_url
               (requires: WHERE owner = 'Nedjagang' AND repo = '<repo-name>')
  user_repos — full_name, description, open_issues_count, updated_at

runbook:
  entries    — id, created_at, service, service_id, summary, root_cause,
               resolution_steps, resolution_minutes, fingerprint

## Mandatory investigation steps (do them in order, skip none)

Step 1 — Query the runbook first. Find similar past incidents:
  SELECT * FROM runbook.entries
  WHERE service_id = '<service_id>' OR service LIKE '%<keyword>%'
  ORDER BY created_at DESC LIMIT 5

Step 2 — Get incident details:
  SELECT id, title, status, urgency, created_at, service__id FROM pagerduty.incidents
  WHERE id = '<incident_id>'

Step 3 — Get on-call responders:
  SELECT user__summary, escalation_policy__summary, start FROM pagerduty.oncalls
  WHERE escalation_level = 1

Step 4 — Check Datadog for unhealthy monitors:
  SELECT id, name, status FROM datadog.monitors WHERE status != 'OK'

Step 5 — Check StatusGator third-party status:
  SELECT display_name, filtered_status FROM statusgator.monitors WHERE board_id = 'g1t0HJdmfr'

Step 6 — Write the postmortem narrative with sections:
  ## Incident Summary | ## Similar Past Incidents | ## Timeline |
  ## Root Cause Analysis | ## Impact | ## Resolution | ## Action Items

Step 7 — Call record_runbook_entry to save the postmortem. This is mandatory.

Keep queries targeted. Do not describe tables you already know from this prompt."""

# Tool definitions — cache_control on last tool caches both the tool list and the system prompt
TOOLS: list[dict[str, Any]] = [
    {
        "name": "coral_query",
        "description": "Run a Coral SQL query and return raw results. Use cross-source JOINs wherever possible. Always alias columns for clarity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute against Coral sources (pagerduty, github, datadog, statusgator schemas).",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "coral_list_tables",
        "description": "List all available tables across every Coral source schema. Call this when you need to discover what data is available.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "coral_describe_table",
        "description": "Describe the columns and types of a specific table in a Coral source schema. Call this before writing a query against an unfamiliar table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {
                    "type": "string",
                    "description": "The source schema name (e.g. 'pagerduty', 'github', 'datadog', 'statusgator', 'runbook').",
                },
                "table": {
                    "type": "string",
                    "description": "The table name within the schema.",
                },
            },
            "required": ["schema", "table"],
        },
    },
    {
        "name": "query_runbook",
        "description": "Query the Living Runbook — a Coral source of past incident postmortems written by this agent. Always call this at the start of every investigation to find similar past incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SQL query against runbook.entries. Columns: id, created_at, service, service_id, summary, root_cause, resolution_steps, resolution_minutes, fingerprint.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "record_runbook_entry",
        "description": "Persist a completed postmortem to the Living Runbook so future investigations can learn from it. Call this at the end of every investigation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id":       {"type": "string", "description": "PagerDuty incident ID."},
                "service":           {"type": "string", "description": "Human-readable service name."},
                "service_id":        {"type": "string", "description": "PagerDuty service ID."},
                "summary":           {"type": "string", "description": "One-sentence description of what happened."},
                "root_cause":        {"type": "string", "description": "Root cause explanation."},
                "resolution_steps":  {"type": "string", "description": "Numbered steps taken to resolve."},
                "resolution_minutes":{"type": "integer","description": "Total time to resolve in minutes."},
                "fingerprint":       {"type": "object", "description": "JSON object with error_type, trigger, symptom keys for future matching."},
            },
            "required": ["incident_id", "service", "service_id", "summary", "root_cause", "resolution_steps", "resolution_minutes", "fingerprint"],
        },
        # Cache control here covers the full tool list + system prompt
        "cache_control": {"type": "ephemeral"},
    },
]

_MOCK_POSTMORTEM = """\
## Incident Summary
| Field | Value |
|---|---|
| **Incident ID** | `{incident_id}` |
| **Mode** | MOCK (set LLM_MODE=haiku or LLM_MODE=sonnet for a real run) |
| **Status** | Simulated — no API call made |

## Timeline
| Time (UTC) | Source | Event |
|---|---|---|
| 09:59:09 | PagerDuty | Incident triggered — Web service 5xx error rate at 12% |
| 09:59:39 | PagerDuty | Responder notified by email |
| 10:01:00 | Datadog | Two monitors enter No Data state (system.load, disk latency) |
| 10:15:00 | GitHub | Hotfix PR #42 merged by on-call engineer |
| 10:22:00 | PagerDuty | Incident resolved |

## Root Cause Analysis
Deployment of PR #41 introduced a misconfigured connection pool size that exhausted
database connections under moderate load, causing upstream 5xx errors.

## Impact
- 12% of web service requests returned HTTP 500 for ~23 minutes
- Estimated 4 200 failed requests

## Resolution
Reverted connection pool config via PR #42 hotfix. Service recovered within 2 minutes of deploy.

## Action Items
- [ ] Add connection pool exhaustion alert to Datadog
- [ ] Add pre-deploy load test to CI for connection pool scenarios
"""


def _execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    try:
        if name == "coral_query":
            return coral_sql(tool_input["sql"])
        elif name == "coral_list_tables":
            return coral_sql(
                "SELECT schema_name, table_name FROM coral.tables ORDER BY schema_name, table_name"
            )
        elif name == "coral_describe_table":
            schema = tool_input["schema"]
            table = tool_input["table"]
            return coral_sql(
                f"SELECT column_name, data_type FROM coral.columns "
                f"WHERE schema_name = '{schema}' AND table_name = '{table}' "
                f"ORDER BY ordinal_position"
            )
        elif name == "query_runbook":
            return coral_sql(tool_input["sql"])
        elif name == "record_runbook_entry":
            entry_id = append_runbook_entry(tool_input)
            return f"Runbook entry {entry_id} recorded successfully."
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


def _mock_investigate(incident_id: str) -> dict[str, Any]:
    """Return a canned postmortem instantly — no API call, no cost."""
    return {
        "incident_id": incident_id,
        "mode": "mock",
        "postmortem": _MOCK_POSTMORTEM.format(incident_id=incident_id),
        "tool_calls": [],
        "turns": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0},
    }


def investigate(incident_id: str, mode: str | None = None) -> dict[str, Any]:
    """Run the agentic loop for a given incident ID and return the postmortem.

    mode overrides the LLM_MODE env var: 'mock' | 'haiku' | 'sonnet'
    """
    effective_mode = mode or LLM_MODE

    if effective_mode == "mock":
        return _mock_investigate(incident_id)

    model = _MODELS.get(effective_mode, _MODELS["sonnet"])
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Investigate PagerDuty incident {incident_id}. "
                "Use Coral SQL to pull the full timeline across all sources, "
                "then write a complete incident postmortem."
            ),
        }
    ]

    tool_calls_made = []
    final_narrative = ""
    turn = 0

    while True:
        turn += 1
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=TOOLS,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                if attempt == 3:
                    raise
                time.sleep(60 * (attempt + 1))

        # Append the full response content (preserves compaction state)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_narrative = block.text
            break

        if response.stop_reason != "tool_use":
            break

        # Process all tool_use blocks and build tool_results
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_output = _execute_tool(block.name, block.input)
            tool_calls_made.append(
                {"tool": block.name, "input": block.input, "output_length": len(tool_output)}
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_output,
                }
            )

        messages.append({"role": "user", "content": tool_results})

        # Safety cap
        if turn >= 30:
            break

    return {
        "incident_id": incident_id,
        "mode": effective_mode,
        "postmortem": final_narrative,
        "tool_calls": tool_calls_made,
        "turns": turn,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
            "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        },
    }
