# KB Pass 2 — Validation (the extracting model is not the final authority)

Pass 1 produced 911 model-extracted, UNVALIDATED knowledge items (77 formulas) in
`kb/knowledge/raw/chNN/chunk_*.json`. Pass 2 gives every item an independent verdict so Pass 3
(synthesis/dedup) builds only on trusted material. **Validation NEVER edits, "fixes," or deletes
knowledge content — it annotates + flags only.** Dedup-before-validation would launder errors into
canonical concepts; recipe order bends to that principle.

## Engine — deterministic-first, LLM judge only on flags
- **Deterministic checks are high-precision, low-recall.** Normalize aggressively before matching (strip
  whitespace/case, unify ×·* → `*`, −– → `-`, etc.). A deterministic **PASS = provisionally trusted**; a
  deterministic **FAIL = candidate for review, NEVER a verdict** (notation varies too much to fail on).
  - `formula_in_source`: each formula's normalized string appears in the item's source-page text.
  - `pages_ok`: pure deterministic — the item's claimed pages fall inside its chapter's span AND the
    item's key terms appear on those pages.
- **Judge (claude -p) only on deterministic FAIL / ambiguous.** It receives the item + its EXACT source
  pages and returns ONLY a JSON verdict: `SUPPORTED | UNSUPPORTED | UNCLEAR` + a one-line reason.
  Three-way, not binary — `UNCLEAR` exists so the judge never guesses.

## Output — annotate in place + separate resumable state
- Write into each item's JSON: `_validation: {formula_in_source, pages_ok, judge_verdict, judge_reason,
  checked_at}` — confidence travels with the object (what Pass 3 filters on).
- `kb/knowledge/validation_state.json` — resumability (rerun the identical command to continue).
- A validation section in the report. NOT a parallel folder — verdicts divorced from items rot.

## Two hard rules (beyond Pass 1's)
- (i) Validation never edits/fixes/deletes content. **UNSUPPORTED items STAY in the KB, marked untrusted,
  until Mike reviews them.**
- (ii) The judge **never rewrites a formula to make it match** — a mismatch is a flag, full stop.

## Tasks (one task = one commit; pause + report each)
1. **Build + pilot on ch17** (Generation Stack — formula-dense). Build `kb/kb_validate.py`; validate ONLY
   ch17; marker-verify a few verdicts by hand (deterministic + judge) against the source pages.
   STOP for Mike's review before the full run.
2. **Full run** (on go): validate all 911 items, resumable. Report verdict counts.
3. **Report + review queue**: validation section; a short **human-review queue = UNSUPPORTED + UNCLEAR
   only, ranked formulas-first** (an invented formula is the worst thing that could reach the Co-Pilot).

## Guardrails
Max 10 iterations. Stop on same failure ×3. Never commit red. No `app.py` edits. **Out of scope:**
synthesis, dedup, RAG folders, embeddings, Co-Pilot wiring (those are Pass 3+).

## Success metric
Every one of the 911 items carries a verdict, and Mike gets a short human-review queue (UNSUPPORTED +
UNCLEAR only) ranked formulas-first.
