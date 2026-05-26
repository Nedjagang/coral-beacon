# Coral Beacon

AI SRE investigator for the Coral hackathon — correlates PagerDuty, Datadog, GitHub, and StatusGator with cross-source Coral SQL.

## WSL setup

Use either workspace path (`/home/ubuntu/coral/coral-beacon` in Cursor WSL, or `/mnt/d/Praneeth/coral/coral-beacon` on D:).

Install the [Coral CLI](https://withcoral.com/docs/getting-started/installation) (Linux: download `coral-x86_64-unknown-linux-gnu.tar.gz` from GitHub releases into `~/.local/bin`).

```bash
cd coral-beacon   # from your repo root

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

chmod +x scripts/run_coral_query.sh
./scripts/run_coral_query.sh queries/list_tables.sql
```

## Run API

```bash
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/health
