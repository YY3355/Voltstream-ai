# KB Loop — Book → Knowledge Base (Pass 1 shipped; Passes 2-5 are future tasks)

Goal: turn *Energy Trading & Investing* (2nd ed.) into typed, source-tagged, rewritten
knowledge objects that the Co-Pilot RAG can retrieve — matching the loop-architecture PDF.

**What exists:** `kb_extract.py` = Pass 1 only (PDF → chapter map → chunks → per-chunk
Claude extraction → `knowledge/raw/chNN/chunk_NNN.json`, resumable state file).
Fixture-tested (probe, dry-run, chunking, verbatim guard, state resumability, manual
chapter override). **Not yet tested on the real book PDF** — that's Task 1.

**What does NOT exist yet (do not claim it does):** chapter synthesis, global dedup/canonical
concepts (the HEAT RATE merge), typed RAG chunk folders, embeddings, Co-Pilot wiring, QA pass.

## Standing rules (from CLAUDE.md ethos)
- Rewrite-don't-copy is enforced in the prompt AND post-hoc (`_verbatim_flags`) — flagged
  items get human review, never silent acceptance. Personal KB from an owned book is fine;
  anything surfaced publicly through Co-Pilot must stay rewritten + attributed.
- Never let the model invent formulas; `{"skip": true}` is a valid, good answer.
- `processing_state.json` is ground truth, not the chat narration.
- Cost gate: --probe estimate → --max-chunks 5 pilot → human review → full run.
  No full burn without explicit go.

## Task order (one task = one commit)
1. **Probe the real book.** `conda run -n volt python kb_extract.py --pdf book.pdf --out knowledge --probe`
   Verify: chapter map matches the actual TOC (human eyeball). If auto-detection is wrong
   (likely — heuristic), write `knowledge/chapters.json` from the TOC and re-probe.
   If "near-empty text" pages are numerous → PDF is scanned → STOP, needs OCR first.
2. **Dry-run.** Eyeball 3-4 previews in `knowledge/dry_run/` — chunks should be coherent
   sections, not shredded mid-formula.
3. **Pilot.** `--max-chunks 5` with ANTHROPIC_API_KEY set. Verify (fresh eyes / subagent):
   JSON valid, items rewritten not copied, no invented formulas vs the source pages,
   source tags correct, actual cost vs estimate. Report before continuing.
4. **Full run** (only on explicit go). Resumable — rerun the same command after any crash.
   Verify: state file shows all chunks done, error count, total spend.
5. **Pass 2 (new build): chapter synthesis + dedup** — merge chunk items per chapter,
   then global canonical concepts with merged source references.
6. **Pass 3 (new build): typed RAG chunks** (`concepts/ formulas/ trading_strategies/ ...`)
   + retrieval metadata; then wire to Co-Pilot behind its existing citation/confidence layer.

Guardrails: max 10 iterations, stop on same failure ×3, never commit red,
no drive-by edits to app.py.
