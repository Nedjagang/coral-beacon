import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.coral_client import coral_sql, coral_sql_file
from agent.investigator import investigate

load_dotenv()

app = FastAPI(title="Coral Beacon")
QUERIES_DIR = Path(__file__).parent / "queries"


class SqlRequest(BaseModel):
    sql: str


def _run(coro_fn):
    try:
        return {"result": coro_fn()}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr) from e


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tables")
def list_tables():
    return _run(lambda: coral_sql_file(str(QUERIES_DIR / "list_tables.sql")))


@app.post("/query")
def run_query(body: SqlRequest):
    return _run(lambda: coral_sql(body.sql))


@app.get("/investigate/{incident_id}")
def investigate_incident(incident_id: str, mode: str | None = None):
    """mode query param: mock | haiku | sonnet  (overrides LLM_MODE env var)"""
    try:
        return investigate(incident_id, mode=mode)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
