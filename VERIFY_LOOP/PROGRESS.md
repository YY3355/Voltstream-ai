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
        commit <pending>.
        LAUNCHD ENV-PASSTHROUGH CONFIRMED → tasks 3/5 need NO rebuild, NO FDA re-grant.
- [ ] 3 — Auto-settle job (JOB=settle agent ~09:00 ET, catch-up loop, commit+push+log).
- [ ] 4 — Notifications scripts/notify.sh (ntfy.sh, NTFY_TOPIC, DRY_RUN).
- [ ] 5 — Watchdog (JOB=watchdog agent ~18:30 ET) reads jobs.jsonl.
- [ ] 6 — Report: equity curve + regime note + backlog flag.
- [ ] 7 — Docs (CLAUDE.md agents/env/caveat) + PROGRESS final state.

## Append-only log
- init (2026-07-25) — Read CLAUDE.md launchd section + dart_journal.py + auto_commit.sh + stub. Wrote
  GOAL.md. Facts: signal files = dart_journal.py+dart_engine.py; live backlog = 07-21,07-22,07-24
  (07-23 missing=missed day); stub passes environ → JOB-env dispatch reuses the one FDA .app (verify via
  kickstart). Starting task 1.
