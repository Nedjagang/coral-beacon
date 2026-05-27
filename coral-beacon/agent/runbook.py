"""Living Runbook writer — appends postmortem entries to data/runbook.jsonl."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

RUNBOOK_PATH = Path(__file__).parent.parent / "data" / "runbook.jsonl"


def append_runbook_entry(fields: dict) -> str:
    """Append a new postmortem entry and return its generated ID."""
    entry = {
        "id": f"rb-{uuid.uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": fields.get("service", ""),
        "service_id": fields.get("service_id", ""),
        "summary": fields.get("summary", ""),
        "root_cause": fields.get("root_cause", ""),
        "resolution_steps": fields.get("resolution_steps", ""),
        "resolution_minutes": int(fields.get("resolution_minutes", 0)),
        "fingerprint": json.dumps(fields.get("fingerprint", {})),
    }
    RUNBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNBOOK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry["id"]
