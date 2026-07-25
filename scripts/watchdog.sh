#!/bin/bash
# ---------------------------------------------------------------------------
# watchdog.sh — daily health check for the DART rhythm (launchd com.voltstream.dartwatchdog,
# ~18:30 ET). Dispatched from auto_commit.sh when JOB=watchdog.
#
# Reads journal/jobs.jsonl + the journal via watchdog_check.py. If today's commit leg is
# missing/failed OR the settle backlog > 1 day, it notifies LOUDLY (high). HEALTHY = SILENT.
# It commits nothing; it only reads + (maybe) notifies, and logs its own run to jobs.jsonl.
#
# Same test seams: CODE_DIR, JOURNAL_REPO, DART_ASOF, DART_FIXTURE (fixture only used to gate the guard).
# NOTE: no `set -e`; the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA="/Applications/ana/anaconda3/bin/conda"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"
REPO="${JOURNAL_REPO:-$CODE_DIR}"
JPATH="$REPO/journal"
LOG="$JPATH/watchdog.log"
JOBS_LOG="$JPATH/jobs.jsonl"

# Constraint-4 guardrail: a fixture (test) run must target a TEMP journal, never the real book.
if [ -n "${DART_FIXTURE:-}" ] && [ "$REPO" = "$HOME/Documents/voltstream-ai" ]; then
  echo "REFUSING: DART_FIXTURE set but JOURNAL_REPO is not a temp journal (REPO=$REPO)" >&2
  exit 3
fi

source "$SCRIPT_DIR/joblog.sh"

JOB="watchdog"
ASOF="${DART_ASOF:-$(date +%F)}"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""
NOTIFY="$SCRIPT_DIR/notify.sh"
mkdir -p "$JPATH"
finish() {
  emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"
  # only the watchdog's OWN malfunction is a job failure; a health ALERT is notified inline below
  if [ "$STATUS" = "failure" ] || [ "$STATUS" = "unknown" ]; then
    bash "$NOTIFY" high "DART watchdog FAILED" "${ERROR:-unexpected exit (status=$STATUS)}"
  fi
}
trap finish EXIT

cd "$REPO" || { STATUS="failure"; ERROR="cd $REPO failed"
  echo "$(date '+%F %T %z') FATAL: cd $REPO failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== watchdog START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

# capture watchdog_check's STDOUT (the verdict) only; conda's stderr noise flows to the log, not the alert
OUT="$(cd "$CODE_DIR" && JOURNAL_DIR="$JPATH" DART_ASOF="$ASOF" "$CONDA" run -n volt python scripts/watchdog_check.py)"
RC=$?
echo "$OUT"
echo "[watchdog_check rc=$RC]"

case "$RC" in
  0)  # healthy -> SILENT
      STATUS="success"
      echo "===== END: healthy — silent — exit 0  utc=$(date -u '+%F %T')Z ====="
      exit 0 ;;
  1)  # unhealthy -> LOUD alert (but the watchdog itself ran fine)
      STATUS="alert"; ERROR="$OUT"
      bash "$NOTIFY" high "DART watchdog ALERT" "$OUT"
      echo "===== END: ALERT sent — exit 0  utc=$(date -u '+%F %T')Z ====="
      exit 0 ;;
  *)  # watchdog itself malfunctioned -> failure (trap notifies)
      STATUS="failure"; ERROR="watchdog_check rc=$RC: $(echo "$OUT" | tail -1)"
      echo "===== END: watchdog_check FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
      exit 1 ;;
esac
