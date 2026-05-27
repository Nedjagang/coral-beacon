"""Coral MCP transport — executes SQL via `coral mcp-stdio` (JSON-RPC over stdio)."""

import json
import os
import subprocess


def _coral_env() -> dict:
    env = os.environ.copy()
    env["CORAL_CONFIG_DIR"] = os.getenv("CORAL_CONFIG_DIR", os.path.expanduser("~/coral-hackathon"))
    return env


def _rpc(proc: subprocess.Popen, msg: dict) -> dict:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def coral_sql_mcp(sql: str) -> str:
    """Run SQL against coral mcp-stdio; returns JSON rows string."""
    stripped = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    ).strip()

    proc = subprocess.Popen(
        ["coral", "mcp-stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=_coral_env(),
    )
    try:
        _rpc(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "coral-beacon", "version": "0.1"},
            },
        })
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n")
        proc.stdin.flush()

        resp = _rpc(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "sql", "arguments": {"sql": stripped}},
        })
        result = resp.get("result", {})
        content = result.get("content", [])
        if result.get("isError") and content:
            raise RuntimeError(content[0].get("text", "Coral MCP error"))
        return content[0]["text"] if content else "{}"
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
