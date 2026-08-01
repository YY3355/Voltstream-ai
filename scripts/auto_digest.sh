#!/bin/bash
# ---------------------------------------------------------------------------
# auto_digest.sh — the evening DAILY DIGEST leg (JOB=digest, launchd com.voltstream.dartdigest,
# ~17:30 ET). Dispatched from auto_commit.sh when JOB=digest.
#
#   1. poll the news sources (news_store.poll) so the digest has fresh headlines   [skipped in DRY_RUN]
#   2. compose the digest (digest.py — TEMPLATED, NO LLM): top headlines w/ links + capture health
#   3. send ONE push via notify.sh (ntfy). Priority = high iff any unknown-vintage doc landed today.
# Commits nothing. Logs to journal/digest.log + one jobs.jsonl row. Failure alerts loud (trap).
#
# Seams: CODE_DIR (python cwd), ARCHIVE_DIR (news.db + forecast manifest root; tests -> temp),
#   DIGEST_ASOF (jobs.jsonl row date), DRY_RUN=1 (skip the live news poll; notify.sh prints only).
# NOTE: no `set -e`; the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA="/Applications/ana/anaconda3/bin/conda"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"
JPATH="${JOURNAL_DIR:-$CODE_DIR/journal}"               # overridable for tests (no real-journal pollution)
LOG="$JPATH/digest.log"
JOBS_LOG="$JPATH/jobs.jsonl"

source "$SCRIPT_DIR/joblog.sh"

JOB="digest"
ASOF="${DIGEST_ASOF:-$(date +%F)}"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""
NOTIFY="$SCRIPT_DIR/notify.sh"
mkdir -p "$JPATH"
finish() {
  emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"
  if [ "$STATUS" = "failure" ] || [ "$STATUS" = "unknown" ]; then
    bash "$NOTIFY" high "Daily digest FAILED" "${ERROR:-unexpected exit (status=$STATUS)}"
  fi
}
trap finish EXIT

cd "$CODE_DIR" || { STATUS="failure"; ERROR="cd $CODE_DIR failed"
  echo "$(date '+%F %T %z') FATAL: cd $CODE_DIR failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== auto_digest START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

# 1) refresh news (live) — skipped in DRY_RUN so a test never hits the network
if [ "${DRY_RUN:-}" = "1" ]; then
  echo "[DRY_RUN] skipping live news poll"
else
  POLL="$("$CONDA" run -n volt python news_store.py poll 2>&1)"
  echo "poll: $POLL"
fi

# 2) compose (templated, no LLM) -> line1=priority, line2=title, rest=body
OUT="$("$CONDA" run -n volt python digest.py 2>&1)"
RC=$?
if [ "$RC" -ne 0 ]; then
  STATUS="failure"; ERROR="digest compose rc=$RC: $(echo "$OUT" | tail -1)"
  echo "$OUT"
  echo "===== END: compose FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi
PRIORITY="$(echo "$OUT" | sed -n 1p)"
TITLE="$(echo "$OUT" | sed -n 2p)"
BODY="$(echo "$OUT" | sed -n '3,$p')"
echo "--- digest (priority=$PRIORITY) ---"; echo "$TITLE"; echo "$BODY"

# 3) one push (notify.sh honors DRY_RUN + a silent no-op when NTFY_TOPIC is unset)
bash "$NOTIFY" "${PRIORITY:-default}" "$TITLE" "$BODY"
STATUS="success"
echo "===== END: digest sent (priority=$PRIORITY) — exit 0  utc=$(date -u '+%F %T')Z ====="
exit 0
