#!/bin/bash
# ---------------------------------------------------------------------------
# auto_kardashev.sh — daily WITNESS capture of Kardashev's /latest (JOB=kardashev, ~16:30 ET,
# after their ~20:06 UTC daily issuance). Dispatched from auto_commit.sh when JOB=kardashev.
#
#   1. fetch /forecast/spread/latest -> research/kardashev_eval/witness/latest_<date>.json + witness_log
#      (vintage = their issued_at + our capture UTC; append-only, idempotent).
#   2. git commit + push the witness file -> the git history is an IMMUTABLE, independently-witnessed
#      record of what their API served each date (makes future scoring attestable by us). Push is
#      best-effort: a push failure still leaves the local commit's immutable timestamp.
# Logs to journal/kardashev.log + one jobs.jsonl row. LOUD ntfy on failure.
#
# Seams: CODE_DIR (repo + python cwd), JOURNAL_DIR (jobs.jsonl/logs; tests -> temp),
#   KARDASHEV_REMOTE (push target; default = repo origin), DRY_RUN=1 (skip fetch + commit).
# NOTE: no `set -e`; the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA="/Applications/ana/anaconda3/bin/conda"
GIT="/usr/bin/git"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"
JPATH="${JOURNAL_DIR:-$CODE_DIR/journal}"
LOG="$JPATH/kardashev.log"
JOBS_LOG="$JPATH/jobs.jsonl"

source "$SCRIPT_DIR/joblog.sh"

JOB="kardashev"
ASOF="${KARDASHEV_ASOF:-$(date +%F)}"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""
NOTIFY="$SCRIPT_DIR/notify.sh"
mkdir -p "$JPATH"
finish() {
  emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"
  if [ "$STATUS" = "failure" ] || [ "$STATUS" = "unknown" ]; then
    bash "$NOTIFY" high "Kardashev witness FAILED" "${ERROR:-unexpected exit (status=$STATUS)}"
  fi
}
trap finish EXIT

cd "$CODE_DIR" || { STATUS="failure"; ERROR="cd $CODE_DIR failed"
  echo "$(date '+%F %T %z') FATAL: cd $CODE_DIR failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== auto_kardashev START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

if [ "${DRY_RUN:-}" = "1" ]; then
  OUT="$("$CONDA" run -n volt python research/kardashev_eval/capture_latest.py --dry 2>&1)"
  echo "[DRY_RUN] $OUT"
  STATUS="dry-run"
  bash "$NOTIFY" default "Kardashev witness DRY_RUN" "would fetch /latest + commit witness"
  echo "===== END: DRY_RUN — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi

# 1) fetch + store the witness
OUT="$("$CONDA" run -n volt python research/kardashev_eval/capture_latest.py 2>&1)"
RC=$?
echo "$OUT"
if [ "$RC" -ne 0 ]; then
  STATUS="failure"; ERROR="capture rc=$RC: $(echo "$OUT" | tail -1)"
  echo "===== END: capture FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi
if echo "$OUT" | grep -q '"already-captured"'; then
  STATUS="already-captured"
  echo "===== END: already captured today — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi

# 2) commit + push the witness (immutable timestamp = the attestation)
"$GIT" add research/kardashev_eval/witness
if "$GIT" diff --cached --quiet -- research/kardashev_eval/witness; then
  STATUS="noop"
  echo "===== END: nothing new to commit — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi
"$GIT" commit -m "kardashev witness (auto) $ASOF" -- research/kardashev_eval/witness
echo "[git commit rc=$?]"
COMMIT_SHA="$("$GIT" rev-parse HEAD)"
"$GIT" push ${KARDASHEV_REMOTE:+"$KARDASHEV_REMOTE" HEAD}
PUSH_RC=$?
echo "[git push rc=$PUSH_RC]"
if [ "$PUSH_RC" -ne 0 ]; then
  # push is best-effort: the local commit already carries the immutable timestamp
  STATUS="success-localonly"; ERROR="push rc=$PUSH_RC (commit $COMMIT_SHA is local-only)"
  bash "$NOTIFY" default "Kardashev witness (local only)" "committed $COMMIT_SHA; push failed rc=$PUSH_RC"
  echo "===== END: committed locally, push failed — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi
STATUS="success"
echo "===== END: witnessed + committed $COMMIT_SHA — exit 0  utc=$(date -u '+%F %T')Z ====="
exit 0
