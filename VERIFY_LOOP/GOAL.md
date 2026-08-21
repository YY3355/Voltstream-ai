# GOAL — KB Pass 2: Validation (supervised verify-loop)

Give every one of the 911 Pass-1 knowledge items an independent verdict (the extracting model is NOT
the final authority), so Pass 3 synthesis/dedup builds only on trusted material. Annotate + flag ONLY —
validation never edits/fixes/deletes content. Supervised: one task = one commit, verify fresh-eyes,
never commit red, pause + check in after every task. Spec: `kb/KB_PASS2_RECIPE.md`.

## Fixed facts
- Book (confirmed, DO NOT read into context): `/Users/mikeoc/Downloads/_OceanofPDF.com_Energy_Trading_and_Investing_-_Davis_W_Edwards.pdf`
- Input: `kb/knowledge/raw/chNN/chunk_*.json` (911 items, 77 formulas). chapters.json = the 34-section map.
- Engine = `claude-cli` (subscription, no API key) for the JUDGE only. Env: `conda run -n volt`.

## Approach (from the recipe)
- **Deterministic-first:** `formula_in_source` (normalized match on source-page text) + `pages_ok` (claimed
  pages inside chapter span + key terms on those pages). PASS = provisionally trusted; FAIL = review
  candidate, never a verdict.
- **Judge (claude -p) only on FAIL/ambiguous:** item + exact source pages → `SUPPORTED|UNSUPPORTED|UNCLEAR`
  + one-line reason. Three-way so it never guesses.
- **Output:** `_validation:{formula_in_source, pages_ok, judge_verdict, judge_reason, checked_at}` in each
  item; `validation_state.json` (resumable); validation report section.

## Two hard rules
(i) Never edit/fix/delete content — UNSUPPORTED items stay, marked untrusted, until Mike reviews.
(ii) The judge never rewrites a formula to match — mismatch = flag, full stop.

## Tasks (STOP + report after each)
1. **Build `kb_validate.py` + pilot ch17** (Generation Stack, formula-dense). Marker-verify a few verdicts
   by hand vs source. ⏸ STOP for Mike's review before the full run.
2. **Full run** (on go): validate all 911 items, resumable; report verdict counts.
3. **Report + review queue:** validation section + human-review queue (UNSUPPORTED + UNCLEAR only,
   formulas-first).

## Out of scope / guardrails
No synthesis, dedup, RAG folders, embeddings, Co-Pilot wiring. No app.py edits. Max 10 iterations, stop on
same failure ×3, never commit red, pause after each task.

## Success metric
All 911 items carry a verdict; a short human-review queue (UNSUPPORTED + UNCLEAR), ranked formulas-first.
