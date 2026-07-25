"""Health check for the DART daily-rhythm — pure inspection, no LLM, no network.

Reads journal/jobs.jsonl + the journal and decides whether the rhythm is healthy:
  - today's COMMIT leg must have a row for `today` with status success | already-committed,
  - the SETTLE backlog (past call-days with no ledger rows) must be <= 1 day.

Prints an alert string and exits 1 if UNHEALTHY; prints a one-line healthy summary and exits 0 if OK.
Seams: JOURNAL_DIR (journal path), DART_ASOF (injectable 'today').
"""
import glob
import json
import os
import sys
import pandas as pd

jdir = os.environ.get("JOURNAL_DIR", "journal")
today = os.environ.get("DART_ASOF") or pd.Timestamp.now().strftime("%Y-%m-%d")
jobs_path = os.path.join(jdir, "jobs.jsonl")
ledger_path = os.path.join(jdir, "ledger.csv")

rows = []
if os.path.exists(jobs_path):
    for line in open(jobs_path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # skip a malformed line rather than crash the health check

# 1) today's commit leg present and healthy?
commit_today = [r for r in rows if r.get("job") == "commit" and r.get("asof_date") == today]
commit_ok = any(r.get("status") in ("success", "already-committed") for r in commit_today)

# 2) settle backlog = past call-days (date < today) with no ledger rows yet
call_days = sorted(os.path.basename(f)[6:16] for f in glob.glob(os.path.join(jdir, "calls_*.json")))
past = [d for d in call_days if d < today]
settled = set()
if os.path.exists(ledger_path):
    settled = set(pd.read_csv(ledger_path)["date"].astype(str))
backlog = [d for d in past if d not in settled]

alerts = []
if not commit_ok:
    alerts.append(f"commit leg for {today}: " + ("commit FAILED" if commit_today else "no run recorded"))
if len(backlog) > 1:
    alerts.append(f"settle backlog {len(backlog)} days ({backlog[0]}..{backlog[-1]})")

if alerts:
    print("; ".join(alerts))
    sys.exit(1)
print(f"healthy: commit {today} ok, settle backlog {len(backlog)} day(s)")
sys.exit(0)
