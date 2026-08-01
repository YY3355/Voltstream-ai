#!/bin/bash
# ---------------------------------------------------------------------------
# auto_capture.sh — the daily FORECAST/OUTAGE CAPTURE leg (the future training data).
# Dispatched from auto_commit.sh when JOB=capture (launchd com.voltstream.dartcapture, ~06:00 ET).
#
#   1. archive-capture the last N complete post-days for all 11 products (idempotent, append-only)
#      into data_archive/forecasts/  — vintage-stamped, NO LLM (forecast_store.py).
#   2. bundle top-up (backfill_bundles_all) — grabs any newly-published month bundle (self-heals the
#      intra-hour trio gap the moment ERCOT posts its bundle; keeps deep products current).
# The archive is GITIGNORED, so this leg COMMITS NOTHING — the data lives on disk like dart_cache/.
# All output + UTC/local timestamps -> journal/capture.log. One structured row -> journal/jobs.jsonl
# (via the EXIT trap, so EVERY path is recorded). LOUD ntfy on failure — a silent capture failure is
# DESTROYED TRAINING DATA (constraint 5). SILENT on success (the daily digest summarizes).
#
# Test seams (tests NEVER hit ERCOT — the backfill owns the ERCOT budget; tests use DRY_RUN):
#   CODE_DIR      where forecast_store.py lives / python cwd   (default ~/Documents/voltstream-ai)
#   ARCHIVE_DIR   archive root (forecast_store reads this)     (tests point at a TEMP dir)
#   CAPTURE_ASOF  injectable 'today' (YYYY-MM-DD) for the jobs.jsonl row
#   CAPTURE_DAYS  trailing complete days to (re)capture        (default 2; >=2 self-heals a miss)
#   DRY_RUN=1     skip the ERCOT pull ENTIRELY — exercise wiring/logging/notify only
#
# NOTE: no `set -e` — exit codes handled explicitly; the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
# resolve our own dir absolutely before the job cd's away (sibling scripts referenced via this)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA="/Applications/ana/anaconda3/bin/conda"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"
JPATH="$CODE_DIR/journal"                                # logs live with the rhythm logs (gitignored)
LOG="$JPATH/capture.log"
JOBS_LOG="$JPATH/jobs.jsonl"
DAYS="${CAPTURE_DAYS:-2}"

source "$SCRIPT_DIR/joblog.sh"

JOB="capture"
ASOF="${CAPTURE_ASOF:-$(date +%F)}"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""                # capture commits nothing (data gitignored)
NOTIFY="$SCRIPT_DIR/notify.sh"
mkdir -p "$JPATH"
finish() {
  emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"
  # loud on ANY failure (incl. an unexpected exit) — a silent capture failure destroys training data
  if [ "$STATUS" = "failure" ] || [ "$STATUS" = "unknown" ]; then
    bash "$NOTIFY" high "Forecast capture FAILED" "${ERROR:-unexpected exit (status=$STATUS)}"
  fi
}
trap finish EXIT

cd "$CODE_DIR" || { STATUS="failure"; ERROR="cd $CODE_DIR failed"
  echo "$(date '+%F %T %z') FATAL: cd $CODE_DIR failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== auto_capture START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

# DRY_RUN: exercise the wiring only — NO ERCOT pull (the backfill owns the budget; tests are offline)
if [ "${DRY_RUN:-}" = "1" ]; then
  echo "[DRY_RUN] would: capture-recent-days $DAYS ALL + backfill-bundles-all ALL into ${ARCHIVE_DIR:-data_archive}/forecasts"
  STATUS="dry-run"
  bash "$NOTIFY" default "Forecast capture DRY_RUN" "would capture last $DAYS days + bundle top-up (11 products)"
  echo "===== END: DRY_RUN — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi

# 1) archive-capture the last N complete days for all products (idempotent, append-only)
OUT="$("$CONDA" run -n volt python forecast_store.py capture-recent-days "$DAYS" ALL 2>&1)"
RC=$?
echo "$OUT"
echo "[capture-recent-days rc=$RC]"
if [ "$RC" -ne 0 ]; then
  STATUS="failure"; ERROR="capture-recent-days rc=$RC: $(echo "$OUT" | tail -1)"
  echo "===== END: capture FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi

# 2) bundle top-up — grab any newly-published month bundle (cheap; skips done months)
OUT2="$("$CONDA" run -n volt python forecast_store.py backfill-bundles-all ALL 2>&1)"
RC2=$?
echo "$OUT2"
echo "[backfill-bundles-all rc=$RC2]"
if [ "$RC2" -ne 0 ]; then
  STATUS="failure"; ERROR="bundle top-up rc=$RC2: $(echo "$OUT2" | tail -1)"
  echo "===== END: bundle top-up FAILED (rc=$RC2) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi

# success = SILENT (the daily digest, Task 8, summarizes captured/misses); failure already alerted
NEW_TOTAL="$(echo "$OUT" | grep -oE "'new': [0-9]+" | grep -oE '[0-9]+' | awk '{s+=$1} END{print s+0}')"
STATUS="success"
echo "===== END: captured (last $DAYS days) new=${NEW_TOTAL:-?} docs + bundle top-up — exit 0  utc=$(date -u '+%F %T')Z ====="
exit 0
