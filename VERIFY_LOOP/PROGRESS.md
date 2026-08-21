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
- [x] 2 — FULL RUN. 911/911 validated (0 missing _validation), no rate-window pause. 817 deterministic-
      pass (provisional); 94 flagged->judged: 40 SUPPORTED / 47 UNSUPPORTED / 7 UNCLEAR. Review queue =
      54 (UNSUPPORTED+UNCLEAR). 61 items carry >=1 formula. ✔
- [x] 3 — REPORT. kb_review_queue.py -> kb/knowledge/review_queue.md: summary, blind-spot named (tokens-
      present != assembled-right), per-chapter flag table, 54-item queue (12 FORMULA-items first, then
      prose), each with why-flagged (43/54 page-attribution, 11 formula) + judge reason, + sampled PASSED
      formulas from ch12/14/30 (blind-spot insurance). Real catch e.g. cube-law wind formula UNSUPPORTED
      (not in source). Every figure from disk; read-only. ✔  LOOP COMPLETE (T1-T3).

## Append-only log
- setup (2026-08-21) — Pass 1 done (911 items, 77 formulas, unvalidated). Mike chose (A) validation over
  (B) synthesis: dedup-before-validation launders errors. Full spec captured in KB_PASS2_RECIPE.md
  (deterministic-first + LLM judge on flags, three-way verdict, annotate-in-place, two hard no-edit rules,
  ch17 pilot gate, review queue formulas-first). Next: build kb_validate.py + pilot ch17, STOP for review.
