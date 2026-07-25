# GOAL — complete the daily-rhythm system around the launchd auto-commit leg

Settle automated, failures loud, record honest. Build the rhythm around the EXISTING commit leg
(scripts/auto_commit.sh → DartAutoCommit.app compiled stub → FDA grant, daily 16:00 ET). Supervised,
max 10 iterations, ONE task/commit, pause+report after each. Never commit red. Same check red 3x = blocked.

## Hard constraints (violating any = RED even if it runs)
1. REGIME DECLARATION — one book, systematic, honestly labeled. journal/ ≤2026-07-22 = manual execution
   of the rules; ≥2026-07-24 = same rules, auto-committed. Every auto-generated calls file from now on
   embeds: `model_version` (git SHA of the signal-logic files at gen time), `generated_by:"auto"`,
   `generated_at` (UTC ISO). NEVER rewrite/amend already-pushed history — 07-24/07-25 files stay as-is;
   regime note lives in README + ledger header; stamps apply GOING FORWARD (07-26+).
2. Never backdate. Commit-leg run after its valid window logs a MISSED day. Settle only settles days
   whose data exists. Git timestamps stay meaningful.
3. Settle is arithmetic: deterministic, NO LLM anywhere in commit or settle paths.
4. Tests NEVER touch real journal/, real ledger, or push to origin. Journal path + remote come from env
   (JOURNAL_DIR, JOURNAL_REMOTE); tests use temp dirs + a throwaway local bare repo as remote.
   Notifications DRY_RUN=1 in tests.
5. Preserve the FDA chain. Prefer editing shell scripts the existing stub invokes over rebuilding the
   .app. If a rebuild is unavoidable: STOP, report, include re-grant steps — never silently ship a job
   TCC will kill.
6. Times: schedule local via launchd; every log line records UTC + local. README notes: launchd only
   runs while Mac awake/on; StartCalendarInterval catches missed runs on wake, but multi-day laptop-off
   = missed days BY DESIGN; Fly migration is the future fix.

## Facts discovered (repo truth)
- Signal-logic files = dart_journal.py (build_calls) + dart_engine.py (fetch_live). model_version =
  their git blob SHAs (git hash-object), so it changes iff signal logic changes.
- dart_journal.py: build_calls (pure), score_calls (pure), cmd_commit/cmd_settle/cmd_report (live).
  JDIR="journal" hardcoded → make env-overridable (JOURNAL_DIR). _dart_history → live network via
  dart_engine.fetch_live → add DART_FIXTURE seam for tests. Add DART_ASOF seam for injectable "now".
- Live settle backlog (ledger ends 07-16): unsettled past days w/ calls = 07-21, 07-22, 07-24
  (07-23 has NO calls file = missed day; 07-25 = today). Catch-up loop DISCOVERS them (no hardcoding).
- Commit stub: DartAutoCommit.app/Contents/MacOS/dart_auto_commit (compiled) → posix_spawn /bin/bash
  scripts/auto_commit.sh with `environ` passed through → launchd plist EnvironmentVariables reach the
  shell. => route new jobs by JOB env in each new plist, REUSING the one FDA .app (no rebuild). VERIFY
  env-passthrough via kickstart before relying on it. Fallback = dispatcher rebuild + re-grant (report).
- Env seams: JOURNAL_DIR, DART_ASOF, DART_FIXTURE (python); JOB, JOURNAL_REPO, JOURNAL_REMOTE, DRY_RUN,
  NTFY_TOPIC (shell). jobs.jsonl gitignored (*.log won't match → add explicit rule or name .jsonl ignored).

## Tasks (in order — ONE per iteration/commit)
1. Regime declaration + stamping: gen path embeds model_version/generated_by/generated_at; README
   "Ledger regime" section + ledger header note (manual ≤7/22, auto ≥7/24, virtual fills/no fees footer).
   Add python env seams (JOURNAL_DIR, DART_ASOF, DART_FIXTURE) needed to test in a temp journal.
   Verify: fixture gen carries stamps; README/ledger text present; git log untouched for old files.
2. Structured job log: append-only journal/jobs.jsonl (gitignored) {job,asof_date,started,ended,status,
   error,commit_sha}; auto_commit.sh writes it. Verify: commit-leg twice in fixture env → 1 success + 1
   already-committed row, valid JSON lines, UTC+local timestamps.
3. Auto-settle job scripts/auto_settle.sh via EXISTING stub (JOB=settle env in a new launchd agent
   ~09:00 ET): settles ALL unsettled past days it has data for (catch-up loop), updates ledger,
   commits+pushes, logs jobs.jsonl. Verify: fixture backlog of 3 → all settle one run, hand-derived P&L
   matches, idempotent 2nd run, kickstart path exercised (env-passthrough confirmed).
4. Notifications scripts/notify.sh: ntfy.sh (NTFY_TOPIC env, silent no-op if unset, DRY_RUN prints):
   commit push success (date+n calls), settle success (day(s)+P&L delta+cumulative), ANY failure (loud+
   error). Verify: DRY_RUN output per event; failure path fires on injected error.
5. Watchdog scripts/watchdog.sh (JOB=watchdog agent ~18:30 ET): reads jobs.jsonl — today's commit
   missing/failed OR settle backlog >1 day → notify loud; healthy = silent. Verify: fixture log missing
   run → fires; healthy → silent; kickstart path exercised.
6. Report update: `report` prints equity curve from settled days + regime note + honesty footer; flags
   committed-but-unsettled days at bottom (backlog always visible). Verify: fixture ledger → correct
   output incl backlog flag.
7. Docs: CLAUDE.md launchd section (all agents, dispatcher/JOB env, env vars, DRY_RUN, laptop-awake
   caveat); PROGRESS.md final state.

## Verification discipline (maker ≠ checker)
- Fresh-eyes subagent per task; independently drives the job with injected DART_ASOF + DART_FIXTURE in a
  temp JOURNAL_DIR + throwaway bare remote; inspects files/stamps/commits/remote/log rows.
- Settle math spot-check: checker re-derives one position's P&L by hand from fixture DA/RT. Pretty
  ledger + wrong number = RED.
- Idempotency: every job twice; 2nd run = no dup commits/rows/notifications.
- Ships a new/changed launchd agent → NOT green until the kickstart (launchd-invoked) path is exercised.

## Out of scope this loop
No briefing job, news, RAG, forecasting, Fly changes. When all green: pause with (a) exact LIVE commands
for Mike to clear the real settle backlog, (b) any FDA re-grant steps IF a rebuild happened. Live
backlog clearing + any real-journal action = MIKE's hands, not mine.
