import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.coral_client import coral_sql, coral_sql_file
from agent.investigator import investigate

load_dotenv()

app = FastAPI(title="Coral Beacon")
QUERIES_DIR = Path(__file__).parent / "queries"
STATIC_DIR = Path(__file__).parent / "static"
LATEST_FILE = Path(__file__).parent / "data" / "latest_investigation.json"


class SqlRequest(BaseModel):
    sql: str


def _run(coro_fn):
    try:
        return {"result": coro_fn()}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr) from e


# ── API routes (must be registered before the static catch-all) ──────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tables")
def list_tables():
    return _run(lambda: coral_sql_file(str(QUERIES_DIR / "list_tables.sql")))


@app.post("/query")
def run_query(body: SqlRequest):
    return _run(lambda: coral_sql(body.sql))


@app.get("/api/latest")
def get_latest():
    """Return the most recently stored investigation result."""
    if not LATEST_FILE.exists():
        raise HTTPException(status_code=404, detail="No investigation has been run yet.")
    return json.loads(LATEST_FILE.read_text())


@app.get("/api/runbook")
def get_runbook():
    """Return all Living Runbook entries via Coral SQL."""
    try:
        raw = coral_sql(
            "SELECT id, created_at, service, service_id, summary, "
            "root_cause, resolution_minutes, fingerprint "
            "FROM runbook.entries ORDER BY created_at DESC"
        )
        # Parse the ASCII table into a list of dicts
        lines = [l for l in raw.strip().splitlines() if l.startswith("|") and "---" not in l]
        if len(lines) < 2:
            return {"entries": []}
        headers = [h.strip() for h in lines[0].strip("|").split("|")]
        entries = []
        for row in lines[1:]:
            values = [v.strip() for v in row.strip("|").split("|")]
            entries.append(dict(zip(headers, values)))
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/investigate/{incident_id}")
def investigate_incident(incident_id: str, mode: str | None = None, transport: str | None = None):
    """mode: mock|haiku|sonnet  transport: subprocess|mcp  (both override env vars)"""
    if transport:
        os.environ["CORAL_TRANSPORT"] = transport
    try:
        result = investigate(incident_id, mode=mode)
        # Persist latest result for the UI
        LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        LATEST_FILE.write_text(json.dumps(result, indent=2))
        return result
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Static files — serves index.html at / ────────────────────────────────────
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
