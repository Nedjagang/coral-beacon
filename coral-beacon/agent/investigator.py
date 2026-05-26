"""Phase 2 — Claude tool_use agent that autonomously chains Coral SQL queries to produce incident postmortems."""

import json
import os
import time
from typing import Any

import anthropic
from dotenv import load_dotenv

from agent.coral_client import coral_sql

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

Your job is to investigate incidents autonomously by querying live operational data across
PagerDuty (incidents, oncalls, escalations), GitHub (pull requests, deployments, commits),
Datadog (metrics, monitors, SLOs), and StatusGator (third-party service statuses).

You have access to Coral SQL — a query engine that JOINs across all these sources using SQL.
Always prefer a single cross-source JOIN over multiple separate queries.

Investigation approach:
1. Start by identifying what the incident is — use coral_list_tables or coral_describe_table if unsure of schema.
2. Pull the incident timeline: when did it start, what service, who was on-call.
3. Correlate with deploys: was a PR merged near the incident start time?
4. Check Datadog: did error rates or latency spike? Do metrics confirm the blast radius?
5. Check StatusGator: was a third-party dependency down at the same time?
6. Synthesize a concise postmortem narrative: timeline, probable root cause, responders, resolution.

Write the final postmortem in this structure:
## Incident Summary
## Timeline
## Root Cause Analysis
## Impact
## Resolution
## Action Items"""

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
                    "description": "The source schema name (e.g. 'pagerduty', 'github', 'datadog', 'statusgator').",
                },
                "table": {
                    "type": "string",
                    "description": "The table name within the schema.",
                },
            },
            "required": ["schema", "table"],
        },
        # Caching here covers both the full tool list and the system prompt
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

        # Safety cap — the agent should never need more than 20 turns
        if turn >= 20:
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
