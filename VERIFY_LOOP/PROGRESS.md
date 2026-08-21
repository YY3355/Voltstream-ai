# Progress — KB Pass 2: Validation

Supervised. Max 10 iters. ONE task = ONE commit. Verify fresh-eyes. Never commit red; same check ×3 = stop.
Pause + report after every task. Judge engine=claude-cli. NO app.py. Annotate+flag ONLY (never edit content).

## Checklist
- [x] 0 — Scope confirmed (A validation, not synthesis). Recipe kb/KB_PASS2_RECIPE.md + GOAL/PROGRESS from
      Mike's paste-ready spec. ✔
- [ ] 1 — Build kb_validate.py (deterministic formula_in_source + pages_ok; claude -p judge on FAIL ->
      SUPPORTED/UNSUPPORTED/UNCLEAR; _validation annotate in place + validation_state.json). PILOT on ch17
      (Generation Stack, formula-dense); marker-verify a few verdicts by hand. ⏸ STOP for Mike's review.
- [ ] 2 — FULL RUN (on go): all 911 items, resumable; verdict counts.
- [ ] 3 — REPORT + review queue (UNSUPPORTED + UNCLEAR, formulas-first).

## Append-only log
- setup (2026-08-21) — Pass 1 done (911 items, 77 formulas, unvalidated). Mike chose (A) validation over
  (B) synthesis: dedup-before-validation launders errors. Full spec captured in KB_PASS2_RECIPE.md
  (deterministic-first + LLM judge on flags, three-way verdict, annotate-in-place, two hard no-edit rules,
  ch17 pilot gate, review queue formulas-first). Next: build kb_validate.py + pilot ch17, STOP for review.
