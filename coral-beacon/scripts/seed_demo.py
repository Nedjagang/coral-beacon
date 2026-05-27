#!/usr/bin/env python3
"""Coral Beacon — demo scenario seed script.

Creates a coherent incident timeline across GitHub, Datadog, and PagerDuty:
  1. GitHub  — repo coral-beacon-demo + PR merged (fix/connection-pool-timeout)
  2. Datadog — web.error.rate metric series climbing to 0.14 over 2 minutes
  3. PagerDuty — P1 incident on Web Service triggered after the deploy

Idempotent: safe to re-run. Each section checks current state first.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --reset   # resolves any open PD incidents first
"""

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

GH_TOKEN      = os.environ["GITHUB_TOKEN"]
GH_OWNER      = "Nedjagang"
GH_REPO       = "coral-beacon-demo"
PD_TOKEN      = os.environ["PAGERDUTY_API_TOKEN"]
PD_FROM_EMAIL = "praneeth.p@aptean.com"
PD_SERVICE_ID = "P017TQH"          # Web Service (from Phase 1 discovery)
DD_API_KEY    = os.environ["DATADOG_API_KEY"]
DD_SITE       = os.getenv("DATADOG_SITE", "us5.datadoghq.com")

GH_HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
PD_HEADERS = {
    "Authorization": f"Token token={PD_TOKEN}",
    "Content-Type": "application/json",
    "From": PD_FROM_EMAIL,
    "Accept": "application/vnd.pagerduty+json;version=2",
}


def section(title: str) -> None:
    print(f"\n── {title} {'─' * (48 - len(title))}")


def log(msg: str) -> None:
    print(f"   {msg}")


# ── GitHub ─────────────────────────────────────────────────────────────────

def _gh(args: list[str], check: bool = True) -> "subprocess.CompletedProcess":
    """Run a gh CLI command and return the result."""
    import subprocess
    return subprocess.run(["gh"] + args, capture_output=True, text=True, check=check)


def seed_github(client: httpx.Client) -> tuple[int, str]:
    """Ensure demo repo exists, branch created, PR merged. Returns (pr_number, merged_at)."""
    section("GitHub")

    # 1. Create repo if missing
    r = client.get(f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}", headers=GH_HEADERS)
    if r.status_code == 404:
        _gh(["repo", "create", f"{GH_OWNER}/{GH_REPO}",
             "--public", "--description", "Coral Beacon demo scenario repository"])
        log(f"Repo created: https://github.com/{GH_OWNER}/{GH_REPO}")
        time.sleep(2)

    # 2a. Already merged? Return early.
    r = client.get(
        f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/pulls",
        headers=GH_HEADERS,
        params={"state": "closed", "per_page": 20},
    )
    for pr in (r.json() if r.is_success else []):
        if pr.get("head", {}).get("ref") == "fix/connection-pool-timeout" and pr.get("merged_at"):
            log(f"PR already merged: #{pr['number']} at {pr['merged_at']}")
            return pr["number"], pr["merged_at"]

    # 2b. Open PR already exists? Skip to merge step.
    r = client.get(
        f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/pulls",
        headers=GH_HEADERS,
        params={"state": "open", "per_page": 20},
    )
    existing_open_pr = None
    for pr in (r.json() if r.is_success else []):
        if pr.get("head", {}).get("ref") == "fix/connection-pool-timeout":
            existing_open_pr = pr
            log(f"Open PR already exists: #{pr['number']}, proceeding to merge")
            break

    if existing_open_pr:
        pr_number = existing_open_pr["number"]
        _gh(["pr", "merge", str(pr_number),
             "--repo", f"{GH_OWNER}/{GH_REPO}",
             "--squash", "--delete-branch", "--yes"])
        merged_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log(f"PR merged: #{pr_number} at {merged_at}")
        return pr_number, merged_at

    # 3. Clone into a temp dir, initialize if empty, create branch + commit + PR
    tmpdir = tempfile.mkdtemp(prefix="coral-beacon-seed-")
    # Remove GITHUB_TOKEN from git subprocess env so the gh credential helper
    # uses the stored gh CLI token (gho_***) rather than the read-only fine-grained PAT.
    git_env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    try:
        repo_url = f"https://github.com/{GH_OWNER}/{GH_REPO}.git"
        subprocess.run(["git", "clone", repo_url, tmpdir], check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "-C", tmpdir, "config", "user.email", "84395513+Nedjagang@users.noreply.github.com"], check=True, env=git_env)
        subprocess.run(["git", "-C", tmpdir, "config", "user.name", "Nedjagang"], check=True, env=git_env)

        # Init main branch if repo is empty (git log fails on an empty clone)
        log_result = subprocess.run(
            ["git", "-C", tmpdir, "log", "--oneline", "-1"], capture_output=True, text=True, env=git_env
        )
        if log_result.returncode != 0 or not log_result.stdout.strip():
            readme = os.path.join(tmpdir, "README.md")
            with open(readme, "w") as f:
                f.write(f"# {GH_REPO}\nCoral Beacon demo scenario repository.\n")
            subprocess.run(["git", "-C", tmpdir, "add", "."], check=True, env=git_env)
            subprocess.run(["git", "-C", tmpdir, "commit", "-m", "chore: initial commit"], check=True, capture_output=True, env=git_env)
            subprocess.run(["git", "-C", tmpdir, "push", "-u", "origin", "main"], check=True, capture_output=True, env=git_env)
            log("Initial commit pushed to main")
            time.sleep(1)

        # Create feature branch
        branch = "fix/connection-pool-timeout"
        subprocess.run(["git", "-C", tmpdir, "checkout", "-b", branch], check=True, capture_output=True, env=git_env)

        # Write the fix file
        cfg_dir = os.path.join(tmpdir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "connection_pool.py"), "w") as f:
            f.write(
                "# connection_pool.py -- Web Service DB config\n"
                "# fix: increased MAX_CONNECTIONS from 10 to 50\n"
                "# Root cause: rb-0001 (2026-05-10) pool exhaustion at >moderate load\n\n"
                "MAX_CONNECTIONS      = 50    # was 10\n"
                "MIN_IDLE             = 5\n"
                "STATEMENT_TIMEOUT_MS = 30_000\n"
                "IDLE_TIMEOUT_MS      = 600_000\n"
                "CONNECT_TIMEOUT_MS   = 5_000\n"
            )
        subprocess.run(["git", "-C", tmpdir, "add", "."], check=True, env=git_env)
        subprocess.run(["git", "-C", tmpdir, "commit", "-m",
                        "fix: increase connection pool MAX_CONNECTIONS from 10 to 50\n\n"
                        "Previous value caused pool exhaustion under moderate load.\n"
                        "Refs: postmortem rb-0001 (2026-05-10)"],
                       check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "-C", tmpdir, "push", "-u", "origin", branch, "--force-with-lease"],
                       check=True, capture_output=True, env=git_env)
        log(f"Branch pushed: {branch}")

        # Create PR via gh CLI
        pr_result = _gh([
            "pr", "create",
            "--repo", f"{GH_OWNER}/{GH_REPO}",
            "--title", "fix: increase connection pool max_connections from 10 to 50",
            "--body", (
                "## Problem\n"
                "Connection pool exhaustion causing 5xx errors on web-service.\n"
                "Same root cause as runbook entry rb-0001 (2026-05-10).\n\n"
                "## Fix\n"
                "Increased MAX_CONNECTIONS from 10 to 50.\n"
            ),
            "--base", "main",
            "--head", branch,
        ])
        # pr_result.stdout is the PR URL, extract number from it
        pr_url = pr_result.stdout.strip()
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
        log(f"PR created: #{pr_number}")
        time.sleep(1)

        # Merge PR
        _gh(["pr", "merge", str(pr_number),
             "--repo", f"{GH_OWNER}/{GH_REPO}",
             "--squash", "--delete-branch", "--yes"])
        merged_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log(f"PR merged: #{pr_number} at {merged_at}")
        return pr_number, merged_at

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Datadog ────────────────────────────────────────────────────────────────

def seed_datadog(client: httpx.Client) -> None:
    """Submit web.error.rate series climbing from 0.01 to 0.14."""
    section("Datadog")
    now = int(time.time())
    points = [
        [now - 150, 0.01],
        [now - 120, 0.03],
        [now - 90,  0.07],
        [now - 60,  0.11],
        [now - 30,  0.14],
        [now,       0.13],
    ]
    r = client.post(
        f"https://api.{DD_SITE}/api/v1/series",
        headers={"DD-API-KEY": DD_API_KEY, "Content-Type": "application/json"},
        json={"series": [{
            "metric": "web.error.rate",
            "type":   "gauge",
            "points": points,
            "tags":   ["service:web-service", "env:demo", "source:coral-beacon"],
            "host":   "web-prod-01",
        }]},
        timeout=15,
    )
    if r.is_success:
        log(f"Metric submitted: web.error.rate — {len(points)} points, peak=0.14")
    else:
        log(f"Metric submit failed (non-fatal): {r.status_code} — {r.text[:120]}")


# ── PagerDuty ──────────────────────────────────────────────────────────────

def resolve_open_incidents(client: httpx.Client) -> None:
    """Resolve any previously seeded demo incidents (for --reset)."""
    r = client.get(
        "https://api.pagerduty.com/incidents",
        headers=PD_HEADERS,
        params={"service_ids[]": PD_SERVICE_ID, "statuses[]": ["triggered", "acknowledged"]},
    )
    for inc in r.json().get("incidents", []):
        client.put(
            f"https://api.pagerduty.com/incidents/{inc['id']}",
            headers=PD_HEADERS,
            json={"incident": {"type": "incident", "status": "resolved"}},
        )
        log(f"Resolved existing incident: {inc['id']}")


def seed_pagerduty(client: httpx.Client, pr_number: int) -> str:
    """Trigger a P1 incident on the Web Service."""
    section("PagerDuty")
    r = client.post(
        "https://api.pagerduty.com/incidents",
        headers=PD_HEADERS,
        json={"incident": {
            "type":    "incident",
            "title":   f"Web service error rate spike 14% — deploy PR #{pr_number}",
            "service": {"id": PD_SERVICE_ID, "type": "service_reference"},
            "urgency": "high",
            "body": {
                "type":    "incident_body",
                "details": (
                    f"web.error.rate climbed from 0.01 to 0.14 starting ~2 minutes after "
                    f"merge of PR #{pr_number} (fix/connection-pool-timeout) into "
                    f"{GH_OWNER}/{GH_REPO}. Datadog shows sustained spike on "
                    f"web.error.rate. Previous identical incident: runbook entry rb-0001."
                ),
            },
        }},
        timeout=15,
    )
    r.raise_for_status()
    inc = r.json()["incident"]
    log(f"Incident created: {inc['id']}")
    log(f"  Title:   {inc['title']}")
    log(f"  Status:  {inc['status']} | Urgency: {inc['urgency']}")
    return inc["id"]


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    reset = "--reset" in sys.argv
    print("\n◈ CORAL BEACON — Demo Seed Script")
    print("  Seeding: GitHub PR → Datadog spike → PagerDuty incident\n")

    with httpx.Client(timeout=30) as client:
        if reset:
            section("Reset: resolving open PD incidents")
            resolve_open_incidents(client)

        pr_number, merged_at = seed_github(client)
        seed_datadog(client)
        incident_id = seed_pagerduty(client, pr_number)

    print(f"""
✅  Demo scenario ready
────────────────────────────────────────────────
   GitHub PR:        #{pr_number} merged in {GH_OWNER}/{GH_REPO}
   PR merged at:     {merged_at}
   Datadog metric:   web.error.rate peaked at 0.14
   PagerDuty:        {incident_id}
────────────────────────────────────────────────
   Investigate (haiku, cheap):
     curl "http://localhost:8000/investigate/{incident_id}?mode=haiku"

   Investigate (sonnet, demo quality):
     curl "http://localhost:8000/investigate/{incident_id}?mode=sonnet"

   Web UI:  http://localhost:8000
""")


if __name__ == "__main__":
    main()
