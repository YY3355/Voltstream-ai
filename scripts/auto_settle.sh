#!/bin/bash
# ---------------------------------------------------------------------------
# auto_settle.sh — the DART journal's SETTLE leg (catch-up).
# Dispatched from auto_commit.sh when JOB=settle (launchd com.voltstream.dartsettle, ~09:00 ET).
#
# Settles ALL unsettled past call-days that have realized data (dart_journal.py settle already
# loops over every pending day whose date < asof and isn't in the ledger). Settlement is PURE
# ARITHMETIC (score_calls) — NO LLM anywhere. Then commits + pushes the updated ledger and logs
# one row to journal/jobs.jsonl. Only settles days whose data exists (never backdates a call).
#
# Same test seams as auto_commit.sh: CODE_DIR, JOURNAL_REPO, JOURNAL_REMOTE, DART_ASOF, DART_FIXTURE.
# NOTE: no `set -e` — exit codes handled explicitly; the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
CONDA="/Applications/ana/anaconda3/bin/conda"
GIT="/usr/bin/git"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"
REPO="${JOURNAL_REPO:-$CODE_DIR}"
JPATH="$REPO/journal"
LOG="$JPATH/settle.log"
JOBS_LOG="$JPATH/jobs.jsonl"

# Constraint-4 guardrail: a fixture (test) run must target a TEMP journal, never the real book.
# Catches an empty/unset JOURNAL_REPO silently falling through to the real repo.
if [ -n "${DART_FIXTURE:-}" ] && [ "$REPO" = "$HOME/Documents/voltstream-ai" ]; then
  echo "REFUSING: DART_FIXTURE set but JOURNAL_REPO is not a temp journal (REPO=$REPO)" >&2
  exit 3
fi

source "$(dirname "$0")/joblog.sh"

JOB="settle"
ASOF="${DART_ASOF:-$(date +%F)}"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""
mkdir -p "$JPATH"
write_row() { emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"; }
trap write_row EXIT

cd "$REPO" || { STATUS="failure"; ERROR="cd $REPO failed"
  echo "$(date '+%F %T %z') FATAL: cd $REPO failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== auto_settle START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

# settle every unsettled past day that has realized data — pure arithmetic, no network beyond price pull.
OUT="$(cd "$CODE_DIR" && JOURNAL_DIR="$JPATH" "$CONDA" run -n volt python dart_journal.py settle 2>&1)"
RC=$?
echo "$OUT"
echo "[dart_journal settle rc=$RC]"

if [ "$RC" -ne 0 ]; then
  STATUS="failure"; ERROR="settle rc=$RC: $(echo "$OUT" | tail -1)"
  echo "===== END: settle FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi

# did the ledger change? (nothing pending -> "nothing to settle", no ledger diff)
"$GIT" add journal
if "$GIT" diff --cached --quiet -- journal; then
  STATUS="noop"
  echo "===== END: nothing new to settle — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi

SETTLED="$(echo "$OUT" | grep -oE 'settled [0-9]{4}-[0-9]{2}-[0-9]{2}' | awk '{print $2}' | tr '\n' ' ')"
SETTLED="${SETTLED% }"
"$GIT" commit -m "DART settlement (auto) ${SETTLED:-days}"
echo "[git commit rc=$?]"
COMMIT_SHA="$("$GIT" rev-parse HEAD)"
"$GIT" push ${JOURNAL_REMOTE:+"$JOURNAL_REMOTE" HEAD}
PUSH_RC=$?
echo "[git push rc=$PUSH_RC]"
if [ "$PUSH_RC" -ne 0 ]; then
  STATUS="failure"; ERROR="push rc=$PUSH_RC (settlement $COMMIT_SHA is local-only)"
  echo "===== END: settled locally but PUSH FAILED (rc=$PUSH_RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi
STATUS="success"
echo "===== END: settled [$SETTLED] + pushed $COMMIT_SHA — exit 0  utc=$(date -u '+%F %T')Z ====="
exit 0
