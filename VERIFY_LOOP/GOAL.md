# GOAL — Book → KB Pass 1 extraction (supervised verify-loop)

Turn *Energy Trading & Investing* (Edwards, 2nd ed.) into typed, source-tagged, REWRITTEN knowledge
objects for the Co-Pilot RAG — Pass 1 only. Supervised: one task = one commit, verify each with FRESH
EYES (marker ≠ maker) before marking done, never commit red, pause + check in after every task.

## Fixed facts
- **Book (confirmed, DO NOT read into context):**
  `/Users/mikeoc/Downloads/_OceanofPDF.com_Energy_Trading_and_Investing_-_Davis_W_Edwards.pdf`
  The script parses it; I never open the PDF myself.
- **Engine = `claude-cli`** (the script default) — extraction runs through `claude -p` on Mike's
  subscription login. NO API key. (Overrides the recipe's older "ANTHROPIC_API_KEY" line.)
- **Env:** `conda run -n volt`. Deps: pypdf 6.16.1 + reportlab 5.0.1 (installed).
- Pipeline: `kb/kb_extract.py` (Pass 1), `kb/kb_report.py` (report), `kb/KB_LOOP_RECIPE.md` (rules).
  Outputs under `kb/knowledge/`.

## Standing rules (from KB_LOOP_RECIPE.md)
- **Rewrite-don't-copy** enforced in-prompt AND post-hoc (`_verbatim_flags`) — flagged items get human
  review, never silent acceptance.
- **Never invent formulas.** `{"skip": true}` is a valid, good answer.
- **`processing_state.json` is ground truth**, not the chat narration. Every report figure comes from disk.
- **Cost gate:** probe → dry-run → `--max-chunks 5` pilot → human review → full run. No full burn without
  Mike's explicit go. (On subscription: the number that matters is chunk count vs the rate-limit window,
  not the $ estimate.)

## Tasks (STOP + report after each)
1. **PROBE** `--probe`: paste detected chapter map vs the actual TOC; if they disagree, write
   `kb/knowledge/chapters.json` from the TOC (1-indexed inclusive) + re-probe until it matches. Many
   near-empty pages → scanned PDF → STOP (OCR is a separate decision). Report chunk count. ⏸ STOP for go.
2. **DRY-RUN** `--dry-run`: read 3-4 previews in `kb/knowledge/dry_run/`; report whether chunks are
   coherent sections (not shredded mid-formula/table). Show one preview.
3. **PILOT** `--max-chunks 5` (fires real `claude -p` — first smoke test of that path; on CLI error report
   exact stderr, no workaround). Verify as MARKER: per output JSON vs its dry-run source — (a) valid
   schema, (b) prose rewritten not copied, (c) every formula appears in source (no inventions), (d) source
   chapter/pages correct, (e) skip used sensibly. Report timing to project the full run. ⏸ STOP for go.
4. **FULL RUN** (only on explicit go): no cap. Resumable — rerun identical command after crash/rate-limit,
   state resumes pending chunks. Report done/error counts. Retry errored once (delete their "error" entries
   from processing_state.json + rerun); still-failing stay recorded as errors (honest scars).
5. **REPORT** `kb_report.py --pdf-out kb/kb_report.pdf`: verify by extracting the PDF text + cross-checking
   its numbers vs processing_state.json (every figure from disk). Caveat section MUST say Pass 1 only /
   unvalidated — do not soften.

## Out of scope (do NOT build this loop)
Pass 2 validation, chapter synthesis, global dedup/canonical concepts, typed RAG folders, Co-Pilot wiring,
embeddings. Separate loops. **No edits to app.py.**

## Guardrails
Max 10 iterations. Stop if the same check fails 3×. Never commit red. Pause + report after every task.
