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
- [DONE] 2 — installed plist + DartAutoCommit.app (compiled stub) + FDA grant. END-TO-END VERIFIED
  (date rolled to 2026-07-23 mid-session, so tomorrow = 2026-07-24):
  (1) PASS kickstart -> real journal/calls_2026-07-24.json (4 hubs, 51 nonzero ±1 calls), commit
      0d75441 "DART calls (auto) 2026-07-24" (msg date == filename), push landed 11d80c5..0d75441,
      auto.log ends "committed + pushed — exit 0". Calls file tracked + on origin/main.
  (2) PASS re-kickstart -> "already committed ... not overwriting" -> exit 0, HEAD+remote unchanged
      (0d75441), single calls file (no dup).
  (3) PASS bootout -> unloaded; bootstrap+enable -> reloaded, schedule intact (Hour 16 Min 0), program
      = the .app stub; post-reload kickstart exit 0 (already-committed), HEAD unchanged.
  KEY LEARNING (now in CLAUDE.md): launchd job vs ~/Documents TCC needs a targeted FDA grant on a
  signed .app whose executable is a COMPILED Mach-O (a script exec is attributed to /bin/bash and the
  grant never applies); children inherit the grant. Rebuild re-signs -> must re-grant FDA.

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
- FDA picker rejects a bare .sh -> user asked to wrap in a .app. BUILT: minimal ad-hoc-signed
  DartAutoCommit.app (~/Library/Application Support/VoltStream/), executable Contents/MacOS/dart_auto_commit
  sources scripts/auto_commit.sh. Reproducible from repo: scripts/install_dartcommit_app.sh +
  scripts/dart_auto_commit_launcher.sh (exec source) + scripts/DartAutoCommit-Info.plist. plist
  ProgramArguments -> the .app executable (direct, so FDA attributes to the bundle). CLAUDE.md updated.
  Verified: install script builds+signs (codesign Identifier=com.voltstream.dartcommit adhoc), Info.plist
  + LaunchAgent plutil OK, agent bootstraps + print points at the .app exec. END-TO-END still PENDING the
  user's FDA grant on DartAutoCommit.app.
- FDA granted to the .app, but kickstart still exit 1: launchd.err.log "Operation not permitted"
  reading the repo script. ROOT CAUSE: a SHELL-SCRIPT bundle exec is run by /bin/bash, so TCC
  attributes to /bin/bash, not the .app -> grant never applies (compiled cprobe confirmed the
  attribution model). FIX: bundle exec must be a COMPILED Mach-O. Rebuilt with scripts/dartcommit_stub.c
  (posix_spawn /bin/bash auto_commit.sh, waits, returns its rc; children inherit the .app FDA). Removed
  obsolete scripts/dart_auto_commit_launcher.sh. install_dartcommit_app.sh now compiles+signs; clean
  bundle verified (Mach-O arm64, codesign --verify --strict OK). CLAUDE.md updated (compiled stub +
  re-sign-invalidates-grant caveat). NOTE: rebuild re-signed the bundle => new cdhash => the earlier FDA
  grant is now STALE; user must remove + re-add the .app in FDA. END-TO-END pending that re-grant.

## Log
- init — GOAL+PROGRESS written. Facts: cmd_commit prints "already committed ... not overwriting" /
  "committed <path>: N ..."; conda /Applications/ana/anaconda3/bin/conda; git /usr/bin/git; HTTPS remote
  (keychain push); TZ America/New_York (Hour=16 == 16:00 ET); auto.log ignored via *.log; dart_cache warm;
  tomorrow 2026-07-23 has NO calls file (fresh path free -> reserve it for the launchd kickstart in task 2).
