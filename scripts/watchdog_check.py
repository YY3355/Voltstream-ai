"""Health check for the DART daily-rhythm — pure inspection, no LLM, no network.

Reads journal/jobs.jsonl + the journal and decides whether the rhythm is healthy:
  - today's COMMIT leg must have a row for `today` with status success | already-committed,
  - the SETTLE backlog (past call-days with no ledger rows) must be <= 1 day,
  - the FORECAST CAPTURE leg must have a good row for `today` — but ONLY once capture is live
    (>=1 capture row ever), so this never false-alarms before the capture job is enabled. A silent
    capture miss is destroyed training data, so a missed/failed capture-for-today is an alert.

Prints an alert string and exits 1 if UNHEALTHY; prints a one-line healthy summary and exits 0 if OK.
Seams: JOURNAL_DIR (journal path), DART_ASOF (injectable 'today').
"""
import glob
import json
import os
import shutil
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

# 3) forecast-capture freshness — only checked once capture is live (>=1 capture row ever), so it
#    can't false-alarm before enablement. Missed/failed capture-for-today = destroyed training data.
capture_rows = [r for r in rows if r.get("job") == "capture"]
capture_today = [r for r in capture_rows if r.get("asof_date") == today]
# 'skipped-lowdisk' counts as a recorded run (the low-disk alert below is the real signal)
capture_ok = any(r.get("status") in ("success", "dry-run", "noop", "skipped-lowdisk")
                 for r in capture_today)

# 4) disk headroom — the capture is the big writer; if free space is below the floor it pauses,
#    which both gaps the training data AND is the early warning that commit/settle could fail.
min_free = float(os.environ.get("FORECAST_MIN_FREE_GB", "10"))
adir = os.environ.get("ARCHIVE_DIR", "data_archive")
try:
    free_gib = shutil.disk_usage(adir if os.path.exists(adir) else ".").free / (1024 ** 3)
except Exception:
    free_gib = None

alerts = []
if not commit_ok:
    alerts.append(f"commit leg for {today}: " + ("commit FAILED" if commit_today else "no run recorded"))
if len(backlog) > 1:
    alerts.append(f"settle backlog {len(backlog)} days ({backlog[0]}..{backlog[-1]})")
if capture_rows and not capture_ok:
    alerts.append(f"forecast capture for {today}: " + ("FAILED" if capture_today else "no run recorded"))
if free_gib is not None and free_gib < min_free:
    alerts.append(f"low disk: {free_gib:.1f}GiB free (< {min_free:.0f} floor) — capture paused; protect commit/settle")

# 5) Kardashev witness freshness — gated on live (>=1 kardashev row ever), so no false alarm pre-enablement
kardashev_rows = [r for r in rows if r.get("job") == "kardashev"]
kardashev_today = [r for r in kardashev_rows if r.get("asof_date") == today]
kardashev_ok = any(r.get("status") in ("success", "success-localonly", "already-captured", "dry-run", "noop")
                   for r in kardashev_today)
if kardashev_rows and not kardashev_ok:
    alerts.append(f"kardashev witness for {today}: " + ("FAILED" if kardashev_today else "no run recorded"))

if alerts:
    print("; ".join(alerts))
    sys.exit(1)
cap_note = f", capture {today} ok" if capture_rows else ", capture not-yet-live"
disk_note = f", disk {free_gib:.0f}GiB free" if free_gib is not None else ""
print(f"healthy: commit {today} ok, settle backlog {len(backlog)} day(s){cap_note}{disk_note}")
sys.exit(0)
