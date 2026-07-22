# GOAL — automate the DART journal COMMIT leg via a launchd agent (settle/report stay MANUAL)

Only the COMMIT leg is automated. settle + report are the judgment leg and stay manual. A macOS
launchd agent runs the commit daily at 16:00 ET (DA posts ~14:30 ET; 16:00 = safe margin).
launchd (NOT cron) because launchd runs MISSED jobs on wake if the Mac was asleep.

## Facts (verified from the repo)
- `python dart_journal.py commit` (cmd_commit): writes journal/calls_<tomorrow>.json; if it already
  exists prints "calls for <d> already committed (<path>) — not overwriting" and RETURNS (writes nothing).
  Success prints "committed <path>: N hub-hour positions for <d>".
- conda: /Applications/ana/anaconda3/bin/conda (full path — launchd has no shell profile).
- git: /usr/bin/git. Remote: HTTPS github.com/YY3355/Voltstream-ai.git -> push uses osxkeychain cred.
- Mac timezone = America/New_York (ET), so launchd Hour=16 == 16:00 ET.
- journal/ IS tracked (calls_*.json committed). journal/auto.log is ALREADY gitignored (*.log rule).
- dart_cache/ warm -> commit's DART pull is fast. Tomorrow = 2026-07-23 (no calls file yet = fresh path free).

## Deliverables
1. scripts/auto_commit.sh (+ chmod +x): cd repo; `<conda> run -n volt python dart_journal.py commit`;
   if output has "already committed" -> exit 0 (manual run earlier that day is fine); else
   `git add journal && git commit -m "DART calls (auto) $(date -v+1d +%F)" && git push`.
   Append ALL output + timestamp to journal/auto.log (gitignored). Full tool paths + PATH for launchd.
2. ~/Library/LaunchAgents/com.voltstream.dartcommit.plist: StartCalendarInterval Hour 16 Minute 0,
   runs /bin/bash scripts/auto_commit.sh. Keep a reference copy in scripts/ for reproducibility.

## Definition of done (== the user's verify)
(1) launchctl load + kickstart manually -> a REAL calls_<tomorrow>.json + git push LAND, auto.log records it.
(2) the already-committed path exits 0 without a duplicate commit/push.
(3) unload / reload survives (job re-registers; kickstart still works).
Push happens for real (this is the point). Keychain cred used for push.

## Verify (fresh eyes — separate maker from checker)
- bash -n + shellcheck (if avail) on the script; plutil -lint on the plist.
- launchctl bootstrap/enable + kickstart; read auto.log; `git log`/`git ls-remote` to confirm push landed.
- Re-kickstart for the already-committed exit-0 path; confirm HEAD unchanged (no dup).
- launchctl bootout + bootstrap again; launchctl print shows it; kickstart works.

## Guardrails
- Supervised. Max 8 iterations. One task = one commit. Never commit red.
- The launchd job does a REAL git push (intended). Do NOT automate settle/report. Do NOT commit auto.log
  or launchd out/err logs (gitignored). Keep the plist out of the repo tree (lives in ~/Library/LaunchAgents),
  reference copy in scripts/ only.
