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

- [blocked-on-user] 2 — TCC hit: launchd kickstart failed exit 126, launchd.err.log =
  "Operation not permitted" reading the repo. DIAGNOSED decisive: launchd-spawned process denied
  ~/Documents by macOS TCC (diag from ~/Library => git-read + ls of repo "Operation not permitted";
  moving script out does NOT help — the git/python WORK is blocked). tccutil can't grant, only reset.
  User chose Option 2 (targeted FDA on a dedicated launcher). BUILT + statically verified:
  * scripts/dart_auto_commit_launcher.sh (repo source) -> installed to
    ~/Library/Application Support/VoltStream/dart_auto_commit_launcher.sh (+x); sources the versioned
    scripts/auto_commit.sh (single source of truth, no drift).
  * plist ProgramArguments = [launcher] DIRECTLY (not /bin/bash) so FDA attributes to the launcher alone.
  * CLAUDE.md "launchd auto-commit" section documents launcher path + TCC/FDA setup for future sessions.
  Verified: bash -n launcher+script OK, plutil -lint OK, agent bootstraps/enables + print shows it points
  at the launcher. END-TO-END (real kickstart -> commit+push) PENDING the user's one-time FDA grant.
  Setup committed as a static-green checkpoint.

## Log
- init — GOAL+PROGRESS written. Facts: cmd_commit prints "already committed ... not overwriting" /
  "committed <path>: N ..."; conda /Applications/ana/anaconda3/bin/conda; git /usr/bin/git; HTTPS remote
  (keychain push); TZ America/New_York (Hour=16 == 16:00 ET); auto.log ignored via *.log; dart_cache warm;
  tomorrow 2026-07-23 has NO calls file (fresh path free -> reserve it for the launchd kickstart in task 2).
