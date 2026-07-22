#!/bin/bash
# ---------------------------------------------------------------------------
# auto_commit.sh — automate the DART journal's COMMIT leg ONLY.
# (settle + report stay MANUAL — that's the judgment leg.)
#
# Run by launchd (com.voltstream.dartcommit) daily at 16:00 ET. It:
#   1. generates tomorrow's calls   -> journal/calls_<tomorrow>.json
#   2. commits + pushes them         (git push uses the existing osxkeychain credential)
# If the calls were already committed earlier today (a manual run), it exits 0 cleanly.
# All output + a timestamp is appended to journal/auto.log (gitignored via *.log).
#
# NOTE: no `set -e` — several steps intentionally return non-zero (grep miss,
# `git diff --quiet`), and we handle exit codes explicitly.
# ---------------------------------------------------------------------------

# launchd gives a minimal environment: set an explicit PATH and use full tool paths.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Applications/ana/anaconda3/bin:$PATH"
CONDA="/Applications/ana/anaconda3/bin/conda"
GIT="/usr/bin/git"
REPO="$HOME/Documents/voltstream-ai"
LOG="$REPO/journal/auto.log"

# dart_journal.py uses relative paths (journal/) — must run from the repo root.
cd "$REPO" || { echo "$(date '+%F %T %Z') FATAL: cd $REPO failed" >>"$LOG" 2>&1; exit 1; }

# From here, append everything (stdout+stderr) to the gitignored log.
exec >>"$LOG" 2>&1
echo ""
echo "===== $(date '+%F %T %Z') auto_commit START (pid $$) ====="

# 1) generate tomorrow's calls (DART pull is disk-cached in dart_cache/)
OUT="$("$CONDA" run -n volt python dart_journal.py commit 2>&1)"
RC=$?
echo "$OUT"
echo "[dart_journal commit rc=$RC]"

# 2a) already committed earlier today -> nothing to do, clean exit
if echo "$OUT" | grep -qi "already committed"; then
  echo "===== END: already committed today — exit 0 (no duplicate) ====="
  exit 0
fi

# 2b) generation failed -> surface it, do NOT commit
if [ "$RC" -ne 0 ]; then
  echo "===== END: commit generation FAILED (rc=$RC) — exit 1 ====="
  exit 1
fi

# 3) commit + push the new calls file
"$GIT" add journal
if "$GIT" diff --cached --quiet -- journal; then
  echo "===== END: nothing new staged under journal/ — exit 0 ====="
  exit 0
fi
"$GIT" commit -m "DART calls (auto) $(date -v+1d +%F)"
echo "[git commit rc=$?]"
"$GIT" push
PUSH_RC=$?
echo "[git push rc=$PUSH_RC]"
if [ "$PUSH_RC" -ne 0 ]; then
  echo "===== END: committed locally but PUSH FAILED (rc=$PUSH_RC) — exit 1 ====="
  exit 1
fi
echo "===== END: committed + pushed — exit 0 ====="
exit 0
