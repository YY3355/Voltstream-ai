# Progress — automate DART journal COMMIT leg (launchd)

Supervised. Max 8 iterations. One task = one commit. settle/report stay MANUAL.

## Tasks
- [done] 1 — scripts/auto_commit.sh (+chmod +x) + reference plist scripts/com.voltstream.dartcommit.plist.
  Full PATH + conda/git absolute paths; cd repo; exec>>auto.log; commit output captured; grep
  "already committed"->exit0; rc!=0->exit1; git add journal, diff --cached --quiet->exit0 else commit
  (msg "DART calls (auto) $(date -v+1d +%F)")+push, push rc!=0->exit1. VERIFIED: bash -n OK, plutil
  -lint OK, conda selftest runs via full path (no calls file made), grep matches real msg, launchd
  .logs gitignored, fresh path preserved. Fresh-eyes subagent GREEN on all 6 (exit-codes, msg/date,
  launchd-env, gitignore, plist, no-hang). Caveat: no timeout on cold DART pull (warm cache mitigates). commit PENDING.
- [todo] 2 — install ~/Library/LaunchAgents/com.voltstream.dartcommit.plist + launchctl load. END-TO-END:
  (1) kickstart -> real calls_2026-07-23.json + git push land + auto.log records;
  (2) re-kickstart -> already-committed exit 0, no dup (HEAD unchanged);
  (3) bootout/bootstrap -> survives, kickstart still works.

## Log
- init — GOAL+PROGRESS written. Facts: cmd_commit prints "already committed ... not overwriting" /
  "committed <path>: N ..."; conda /Applications/ana/anaconda3/bin/conda; git /usr/bin/git; HTTPS remote
  (keychain push); TZ America/New_York (Hour=16 == 16:00 ET); auto.log ignored via *.log; dart_cache warm;
  tomorrow 2026-07-23 has NO calls file (fresh path free -> reserve it for the launchd kickstart in task 2).
