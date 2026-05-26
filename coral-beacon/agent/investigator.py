"""Phase 2 — Claude tool_use agent that autonomously chains Coral SQL queries to produce incident postmortems."""

import json
import os
import time
from typing import Any

import anthropic
from dotenv import load_dotenv

from agent.coral_client import coral_sql

load_dotenv()

MODEL = "claude-sonnet-4-6"

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


def investigate(incident_id: str) -> dict[str, Any]:
    """Run the agentic loop for a given incident ID and return the postmortem."""
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
                    model=MODEL,
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
            # Extract the final text narrative
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
