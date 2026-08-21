# GOAL — KB Pass 3: chapter synthesis + global dedup → canonical KB (supervised loop)

Merge the 857 TRUSTED Pass-2 items into canonical, auditable knowledge objects matching the loop-
architecture archetype (`~/Downloads/energy_book_rag_loop_architecture.pdf`). One task = one commit,
verify fresh-eyes, never commit red, pause for Mike's go at every STOP. Max 10 iters, stop on ×3.

## Input contract (HARD)
- Synthesize ONLY items whose `_validation` is trusted: **deterministic-pass OR judge SUPPORTED** (857).
- EXCLUDE UNSUPPORTED/UNCLEAR/anything in review_queue.md (54) — **excluded, not deleted**. Write the
  excluded list to `kb/knowledge/excluded_from_pass3.json` (nothing silently vanishes).
- **Re-runnable:** when Mike clears the review queue, Pass 3 must fold newly-trusted items in. Design the
  trusted/excluded split to be recomputed from `_validation` each run (never hard-coded).

## Synthesis rules (NON-NEGOTIABLE)
- Merging COMBINES existing validated content — **never writes new claims/formulas/numbers.**
- Every canonical object carries **ALL merged source references** (chapter + pages from each contributing
  item) + a **validation rollup**.
- **Conflicting formulas/definitions for the same concept → do NOT resolve or average.** Record a
  **contradiction flag** with both versions + their sources; contradictions go to a human-review file.
- **Chapter summaries = short, rewritten orientation paragraphs**, not stitched item text.
- Architecture non-negotiables: don't invent; keep provenance after dedup; separate source-supported vs
  inference; preserve units/dimensions; atomic objects over oversized chunks; no long copied passages.

## Tasks (STOP + report at each)
1. **DESIGN + DRY GROUPING (no LLM):** build kb_synthesize.py's grouping stage — normalize topic strings
   (case/punct/plurals/aliases; "heat rate" vs "implied heat rate" stay SEPARATE unless identical
   concept). Output `merge_plan.json` + readable summary: 857 items → N canonical concepts, the 10 biggest
   merge groups (expect heat rate, LMP, spark spread, VaR to lead — if not, something's off). Verify 5
   spot-checked groups: no false merges. ⏸ STOP.
2. **PILOT MERGE (claude -p):** merge step on Part 4 only (ch16-25, generation/power — densest overlap).
   Each call gets grouped items → one canonical object (merged key_points/relationships/implications, all
   formulas verbatim w/ sources, contradiction flags, nothing invented). Marker-verify 5: every claim
   traces to a contributing item, all source refs survived, ≥1 similar-but-distinct pair stayed unmerged.
   Report canonical count + contradictions. ⏸ STOP.
3. **FULL SYNTHESIS (on go):** all chapters, then global cross-chapter pass. Resumable; rate-window pauses
   fine, rerun same command.
4. **STRUCTURE + OUTPUTS:** `kb/energy_knowledge_base/` — concepts/ definitions/ formulas/ market_mechanics/
   trading_implications/ risk/ examples/ chapter_summaries/ + taxonomy.json, concept_graph.json (nodes =
   canonical concepts, edges = only relationships PRESENT in objects, no invented edges),
   contradictions_review.md. Verify: counts reconcile (trusted in = canonical out + excluded; nothing
   lost/conjured); 5 random canonical objects re-checked for provenance.
5. **REPORT:** extend kb_report.py / add kb_synth_report.py → PDF: canonical count, merge stats, top-10
   concepts by source breadth, contradictions, excluded count + reason, honest caveat (synthesis complete,
   review queue OPEN, Pass 5-6 NOT built, Co-Pilot NOT wired).

## Out of scope (do NOT build)
Embeddings, vector DB, retrieval code, Pass-6 evaluation, Co-Pilot wiring, newsletter/live-data layers,
review-queue triage (Mike's), app.py.
