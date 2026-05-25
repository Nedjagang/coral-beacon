# Coral Beacon

AI SRE investigator for the Coral hackathon — correlates PagerDuty, Datadog, GitHub, and StatusGator with cross-source Coral SQL.

## WSL setup

```bash
ls /mnt/d/Praneeth/coral/coral-beacon
cd /mnt/d/Praneeth/coral/coral-beacon

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
