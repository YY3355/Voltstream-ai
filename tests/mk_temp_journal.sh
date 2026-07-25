#!/bin/bash
# Create a throwaway journal git repo + bare remote for testing the daily-rhythm jobs.
# NEVER touches the real journal. Prints two lines:  WORK=<path>  and  BARE=<path>.
# Optional args: paths to calls_*.json files to seed into the journal (for settle-backlog tests).
set -euo pipefail
GIT=/usr/bin/git
WORK="$(mktemp -d)"
BARE="$(mktemp -d)/remote.git"
"$GIT" init -q -b main "$WORK"
"$GIT" -C "$WORK" config user.email test@example.com
"$GIT" -C "$WORK" config user.name "Test Harness"
mkdir -p "$WORK/journal"
echo "throwaway test journal" > "$WORK/journal/.keep"
# mirror the real repo's journal ignore rules so the test is faithful: the runtime log files
# (jobs.jsonl, *.log) must NOT be committed, else `git add journal` makes every run non-idempotent.
printf 'journal/jobs.jsonl\njournal/*.log\n' > "$WORK/.gitignore"
for f in "$@"; do cp "$f" "$WORK/journal/"; done
"$GIT" -C "$WORK" add .gitignore journal
"$GIT" -C "$WORK" commit -q -m "init test journal"
"$GIT" init -q --bare "$BARE"
"$GIT" -C "$WORK" remote add origin "$BARE"
"$GIT" -C "$WORK" push -q origin main
echo "WORK=$WORK"
echo "BARE=$BARE"
