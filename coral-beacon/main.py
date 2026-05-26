import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.coral_client import coral_sql, coral_sql_file

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


@app.get("/investigate/deploys")
def investigate_deploys():
    return _run(
        lambda: coral_sql_file(str(QUERIES_DIR / "incidents_with_deploys.sql"))
    )
