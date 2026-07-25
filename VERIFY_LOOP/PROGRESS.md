# Progress — daily-rhythm system (settle auto, failures loud, record honest)

Supervised. Max 10 iterations. ONE task/commit. settle=arithmetic, no LLM in commit/settle. Never commit red.

## Checklist
- [x] 1 — Regime declaration + stamping + README/ledger note + env seams. VERIFIED (fresh-eyes GREEN
        6/6): stamps correct (UTC≠local, model_version==git hash-object of signal files), real journal
        untouched (07-24 still 0d75441), pure core pure, DART_FIXTURE → 0 dart_engine/gridstatus imports,
        docs honest, already-committed guard holds. commit ec53751.
- [x] 2 — Structured job log journal/jobs.jsonl + scripts/joblog.sh; auto_commit.sh writes one row/run
        via EXIT trap {job,asof_date,started,ended,status,error,commit_sha}, tz-offset ts (UTC+local).
        Added CODE_DIR/JOURNAL_REPO/JOURNAL_REMOTE seams + tests/mk_temp_journal.sh harness. FIXED a bug
        the test caught: commit msg now derives TOMORROW from ASOF (matched file). VERIFIED: self (2-run
        success+already-committed) + LAUNCHD env-passthrough via test-agent kickstart (temp journal, real
        untouched) => confirms JOB-env dispatch works with NO .app rebuild. Fresh-eyes GREEN 5/5 (success/
        idempotent, honest failure row, gitignored, JSON-escape robust, no regression, trap on cd/push fail).
        Non-blocking: cd-fail where $REPO/journal itself is unreachable can't write the row (inherent).
        commit b7fcf7c.
        LAUNCHD ENV-PASSTHROUGH CONFIRMED → tasks 3/5 need NO rebuild, NO FDA re-grant.
- [x] 3 — Auto-settle job scripts/auto_settle.sh (dispatched from auto_commit.sh on JOB=settle;
        com.voltstream.dartsettle plist ~09:00 ET, reuses the FDA .app — NO rebuild). Catch-up settle
        (pure arithmetic), commit+push ledger, jobs.jsonl row. Added constraint-4 GUARD (fixture run
        must target temp journal, else exit 3) after a test misfire showed empty JOURNAL_REPO falls
        through to real (no data harmed — hub mismatch — cleaned up stray gitignored files). Fixed
        harness: temp repo now carries a faithful .gitignore (jobs.jsonl/*.log) so idempotency is real.
        VERIFIED: self (3-day backlog→+21, idempotent, JOB=settle kickstart via launchd) + fresh-eyes
        GREEN 6/6 (P&L hand-recomputed, idempotent, never-backdate skips no-data day, no LLM, guard,
        real untouched). commit 12b32f3. Real settle agent NOT installed — Mike's live action.
- [x] 4 — Notifications scripts/notify.sh (ntfy.sh; NTFY_TOPIC unset=silent no-op; DRY_RUN=1 prints;
        always exit 0 — can't fail a job). Wired: commit success (date+n calls), settle success (days+
        P&L delta+cumulative, from ledger arithmetic), ANY failure loud via the EXIT trap (high). No
        notify on routine no-ops (already-committed / settle noop). FIXED: NOTIFY/joblog/dispatch now use
        an absolute SCRIPT_DIR (relative $0 broke after the job cd'd away). VERIFIED self + fresh-eyes
        GREEN 6/6 incl. launchd-path kickstart showing the settle notice. commit 45fdd1c.
- [x] 5 — Watchdog scripts/watchdog.sh + watchdog_check.py (JOB=watchdog agent ~18:30 ET; dispatched
        via the same stub). Reads jobs.jsonl + journal: alerts HIGH if today's commit missing/failed OR
        settle backlog >1 day; healthy=SILENT. Read-only (no commit/push), no LLM, guard present. FIXED
        conda-stderr-noise leaking into the alert (capture stdout only). VERIFIED self (healthy/missing/
        failed/backlog>1/backlog==1 grace/settled-excluded + JOB=watchdog kickstart) + fresh-eyes GREEN
        7/7 (incl. exact >1 threshold, clean message, launchd path). commit 8fae90b.
- [x] 6 — Report: cmd_report now prints regime note (manual ≤7/22 / auto ≥7/24, stamped), an equity
        curve (sparkline + per-day day/cum), the honesty footer, and an always-visible committed-but-
        UNSETTLED backlog flag (⚠ / ✓) using strict date<today. Read-only, no LLM. VERIFIED self (fixture
        cum +7→+14, real ledger -22.80 + backlog 21/22/24) + fresh-eyes GREEN 6/6 (equity math, backlog
        boundary, regime/footer, no-ledger path, read-only, real-data). commit f8240a3.
- [x] 7 — Docs: CLAUDE.md launchd section rewritten as "launchd daily rhythm" — 3 agents (commit 16:00 /
        settle 09:00 / watchdog 18:30), JOB dispatcher + one-.app design, jobs/helpers, jobs.jsonl schema,
        notifications (NTFY_TOPIC/DRY_RUN), provenance+regime, env seams + test harness + guard, laptop-
        awake caveat; plist bullet covers all 3 + install/manage. TCC/FDA detail preserved. commit <pending>.

## FINAL STATE — all 7 tasks GREEN (each fresh-eyes verified; kickstart exercised where an agent shipped)
- commit + settle + watchdog all run off the ONE FDA-granted DartAutoCommit.app via JOB dispatch — NO
  .app rebuild, NO FDA re-grant this loop (the fragile TCC/FDA chain untouched). report stays manual.
- LIVE PROOF: the real 16:00 commit agent fired mid-loop → 2b993cd "DART calls (auto) 2026-07-26", the
  FIRST stamped auto file (generated_by:auto, model_version 05e0de48…+46b8984d…). Regime stamping works
  in production.
- NOT installed by me (Mike's live action): the dartsettle + dartwatchdog agents, and clearing the REAL
  settle backlog (07-21, 07-22, 07-24). Notifications OFF until Mike sets NTFY_TOPIC. See handoff.

## Append-only log
- init (2026-07-25) — Read CLAUDE.md launchd section + dart_journal.py + auto_commit.sh + stub. Wrote
  GOAL.md. Facts: signal files = dart_journal.py+dart_engine.py; live backlog = 07-21,07-22,07-24
  (07-23 missing=missed day); stub passes environ → JOB-env dispatch reuses the one FDA .app (verify via
  kickstart). Starting task 1.
