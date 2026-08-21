# Progress — KB Pass 2: Validation

Supervised. Max 10 iters. ONE task = ONE commit. Verify fresh-eyes. Never commit red; same check ×3 = stop.
Pause + report after every task. Judge engine=claude-cli. NO app.py. Annotate+flag ONLY (never edit content).

## Checklist
- [x] 0 — Scope confirmed (A validation, not synthesis). Recipe kb/KB_PASS2_RECIPE.md + GOAL/PROGRESS from
      Mike's paste-ready spec. ✔
- [x] 1 — Built kb_validate.py + piloted ch17. 26/26 items validated, all deterministic-pass (0 flags ->
      0 judge calls; genuinely clean chapter). Marker-verify: (1) both ch17 formulas' tokens all in source
      (true pass), (2) pages_ok CAN fail (corrupt->False), (3) judge smoke-tested both ways: real+real
      pages=SUPPORTED, real+wrong pages=UNSUPPORTED (correct, no rubber-stamp, no formula rewrite).
      Annotate-in-place + state work; content untouched. ⏸ STOP for Mike's review before full run.
- [ ] 2 — FULL RUN (on go): all 911 items, resumable; verdict counts.
- [ ] 3 — REPORT + review queue (UNSUPPORTED + UNCLEAR, formulas-first).

## Append-only log
- setup (2026-08-21) — Pass 1 done (911 items, 77 formulas, unvalidated). Mike chose (A) validation over
  (B) synthesis: dedup-before-validation launders errors. Full spec captured in KB_PASS2_RECIPE.md
  (deterministic-first + LLM judge on flags, three-way verdict, annotate-in-place, two hard no-edit rules,
  ch17 pilot gate, review queue formulas-first). Next: build kb_validate.py + pilot ch17, STOP for review.
