import os
import subprocess


def coral_sql(sql: str) -> str:
    """Execute SQL via subprocess (default) or MCP, depending on CORAL_TRANSPORT env var."""
    if os.getenv("CORAL_TRANSPORT", "subprocess").lower() == "mcp":
        from agent.coral_mcp_client import coral_sql_mcp
        return coral_sql_mcp(sql)
    return _coral_sql_subprocess(sql)


def _coral_sql_subprocess(sql: str) -> str:
    env = os.environ.copy()
    env["CORAL_CONFIG_DIR"] = os.getenv(
        "CORAL_CONFIG_DIR", os.path.expanduser("~/coral-hackathon")
    )
    # Coral CLI treats leading '--' as a flag; strip SQL comment lines first
    stripped = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    ).strip()
    result = subprocess.run(
        ["coral", "sql", stripped],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


def coral_sql_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return coral_sql(f.read())
