#!/bin/bash
# ---------------------------------------------------------------------------
# auto_commit.sh — the DART journal's COMMIT leg (generate + commit + push tomorrow's calls).
# Run by launchd (com.voltstream.dartcommit) daily at 16:00 ET via the DartAutoCommit.app stub.
#
#   1. generate tomorrow's calls   -> journal/calls_<tomorrow>.json  (stamped: model_version/auto/UTC)
#   2. commit + push them          (git push uses the existing osxkeychain credential)
# Already committed earlier today -> clean exit 0. All output + UTC/local timestamp -> journal/auto.log.
# One structured row per run -> journal/jobs.jsonl (via the EXIT trap, so EVERY path is recorded).
#
# Test seams (constraint 4 — never touch the real book in tests):
#   CODE_DIR       where dart_journal.py lives / python cwd  (default ~/Documents/voltstream-ai)
#   JOURNAL_REPO   git working tree the journal is committed in (default = CODE_DIR)
#   JOURNAL_REMOTE git push target                          (default: the repo's configured origin)
#   DART_ASOF      injectable 'now' (YYYY-MM-DD)            -> python (never backdates)
#   DART_FIXTURE   realized-DART CSV (no network)           -> python
#
# NOTE: no `set -e` — several steps intentionally return non-zero (grep miss, `git diff --quiet`);
# exit codes are handled explicitly, and the EXIT trap always writes the jobs.jsonl row.
# ---------------------------------------------------------------------------

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"

# resolve our own dir to an ABSOLUTE path up front — the job cd's away later, so sibling scripts
# (joblog.sh, notify.sh, auto_settle.sh) must be referenced absolutely, not via a relative $0.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---- dispatch -------------------------------------------------------------------------------
# This file is the DartAutoCommit.app stub's fixed entry point. Non-commit jobs (set via JOB in
# the launchd plist's EnvironmentVariables) are routed to their scripts, reusing the ONE
# FDA-granted .app — no rebuild, no re-grant. `exec` keeps the same process under the .app's TCC
# grant. Default JOB=commit falls through to the commit leg below.
case "${JOB:-commit}" in
  commit) : ;;
  settle)   exec /bin/bash "$SCRIPT_DIR/auto_settle.sh" ;;
  watchdog) exec /bin/bash "$SCRIPT_DIR/watchdog.sh" ;;
  capture)  exec /bin/bash "$SCRIPT_DIR/auto_capture.sh" ;;
  digest)   exec /bin/bash "$SCRIPT_DIR/auto_digest.sh" ;;
  kardashev) exec /bin/bash "$SCRIPT_DIR/auto_kardashev.sh" ;;
  *) echo "auto_commit: unknown JOB=$JOB" >&2; exit 2 ;;
esac
# ---------------------------------------------------------------------------------------------

CONDA="/Applications/ana/anaconda3/bin/conda"
GIT="/usr/bin/git"
CODE_DIR="${CODE_DIR:-$HOME/Documents/voltstream-ai}"   # real code (signal files) — python runs here
REPO="${JOURNAL_REPO:-$CODE_DIR}"                        # git tree holding the journal
JPATH="$REPO/journal"                                    # absolute journal dir
LOG="$JPATH/auto.log"
JOBS_LOG="$JPATH/jobs.jsonl"

# Constraint-4 guardrail: a fixture (test) run must target a TEMP journal, never the real book.
# Catches an empty/unset JOURNAL_REPO silently falling through to the real repo.
if [ -n "${DART_FIXTURE:-}" ] && [ "$REPO" = "$HOME/Documents/voltstream-ai" ]; then
  echo "REFUSING: DART_FIXTURE set but JOURNAL_REPO is not a temp journal (REPO=$REPO)" >&2
  exit 3
fi

source "$SCRIPT_DIR/joblog.sh"

# --- structured job-log row: set as we go, written once by the EXIT trap -------------------
JOB="commit"
ASOF="${DART_ASOF:-$(date +%F)}"
# tomorrow derived FROM asof, so the commit message always matches the calls file it writes
TOMORROW="$(date -j -v+1d -f '%Y-%m-%d' "$ASOF" '+%Y-%m-%d' 2>/dev/null || date -v+1d +%F)"
STARTED="$(date +%FT%T%z)"
STATUS="unknown"; ERROR=""; COMMIT_SHA=""
NOTIFY="$SCRIPT_DIR/notify.sh"
mkdir -p "$JPATH"
finish() {
  emit_job_row "$JOBS_LOG" "$JOB" "$ASOF" "$STARTED" "$STATUS" "$ERROR" "$COMMIT_SHA"
  # loud on ANY failure (incl. an unexpected exit) — success is notified inline
  if [ "$STATUS" = "failure" ] || [ "$STATUS" = "unknown" ]; then
    bash "$NOTIFY" high "DART commit FAILED" "${ERROR:-unexpected exit (status=$STATUS)}"
  fi
}
trap finish EXIT

# git ops run in the journal repo
cd "$REPO" || { STATUS="failure"; ERROR="cd $REPO failed"
  echo "$(date '+%F %T %z') FATAL: cd $REPO failed" >>"$LOG" 2>&1; exit 1; }

exec >>"$LOG" 2>&1
echo ""
echo "===== auto_commit START  local=$(date '+%F %T %z')  utc=$(date -u '+%F %T')Z  (pid $$) ====="

# 1) generate tomorrow's calls — python runs in CODE_DIR (so signal files + git hash-object resolve),
#    writing into this repo's journal via JOURNAL_DIR. DART_ASOF/DART_FIXTURE pass through the env.
OUT="$(cd "$CODE_DIR" && JOURNAL_DIR="$JPATH" "$CONDA" run -n volt python dart_journal.py commit 2>&1)"
RC=$?
echo "$OUT"
echo "[dart_journal commit rc=$RC]"

# 2a) already committed earlier today -> nothing to do, clean exit
if echo "$OUT" | grep -qi "already committed"; then
  STATUS="already-committed"
  echo "===== END: already committed today — exit 0 (no duplicate)  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi

# 2b) generation failed -> surface it, do NOT commit
if [ "$RC" -ne 0 ]; then
  STATUS="failure"; ERROR="commit generation rc=$RC: $(echo "$OUT" | tail -1)"
  echo "===== END: commit generation FAILED (rc=$RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi

# 3) commit + push the new calls file
"$GIT" add journal
if "$GIT" diff --cached --quiet -- journal; then
  STATUS="noop"
  echo "===== END: nothing new staged under journal/ — exit 0  utc=$(date -u '+%F %T')Z ====="
  exit 0
fi
"$GIT" commit -m "DART calls (auto) $TOMORROW"
echo "[git commit rc=$?]"
COMMIT_SHA="$("$GIT" rev-parse HEAD)"
"$GIT" push ${JOURNAL_REMOTE:+"$JOURNAL_REMOTE" HEAD}
PUSH_RC=$?
echo "[git push rc=$PUSH_RC]"
if [ "$PUSH_RC" -ne 0 ]; then
  STATUS="failure"; ERROR="push rc=$PUSH_RC (commit $COMMIT_SHA is local-only)"
  echo "===== END: committed locally but PUSH FAILED (rc=$PUSH_RC) — exit 1  utc=$(date -u '+%F %T')Z ====="
  exit 1
fi
STATUS="success"
NCALLS="$(echo "$OUT" | grep -oE '[0-9]+ hub-hour positions' | grep -oE '^[0-9]+')"
bash "$NOTIFY" default "DART calls committed" "$TOMORROW: ${NCALLS:-?} calls"
echo "===== END: committed + pushed $COMMIT_SHA — exit 0  utc=$(date -u '+%F %T')Z ====="
exit 0
