# Progress — KB Pass 3: chapter synthesis + global dedup

Supervised. Max 10 iters. ONE task = ONE commit. Verify fresh-eyes. Never commit red; same check ×3 = stop.
Pause for Mike's go at every STOP. Merge=combine-only (never invent). Judge/merge engine=claude-cli. No app.py.

## Input contract
857 TRUSTED (det-pass or SUPPORTED) synthesized; 54 EXCLUDED (47 UNSUPPORTED + 7 UNCLEAR) -> not deleted,
listed in excluded_from_pass3.json. Recomputed from _validation each run (re-runnable when queue clears).

## Checklist
- [x] 0 — Read KB_LOOP_RECIPE.md + loop-architecture PDF (archetype: synthesis loop, HEAT RATE dedup,
      non-negotiables, final /energy_knowledge_base layout). Trusted/excluded split = 857/54. GOAL/PROGRESS. ✔
- [x] 1 — DESIGN + DRY GROUPING (no LLM). Exact-match under-merged (15); switched to curated SEED list
      (28 concepts, canonical->variants, longest-match + WHOLE-WORD). 857 -> 733 canonical (26 seed
      concepts / 24 multi-item merges / 707 honest singletons). Head leads as expected: mark-to-market 13,
      VaR 12, wheeling 12, black-scholes/spark-spread/weather-deriv 9, heat rate 7. Gate artifact
      merge_plan_review.md (seed list + assigned topics). Verified 6 groups no-false-merge: var variant
      safe (no variance/variability), implied heat rate SEPARATE from heat rate, spark/dark/crack never
      cross. excluded_from_pass3.json (54). LMP genuinely absent (confirmed). ⏸ STOP for Mike's review.
- [x] 2 — PILOT MERGE Part 4 (9 groups). Machinery: merge_group (formulas+refs+rollup DETERMINISTIC,
      LLM merges prose only) + MANDATORY post-merge judge + Pass-1 resumability + circuit-breaker(>50%).
      Marker-verify (subagent): caught wheeling inventing "between the 3 interconnects" -> tightened
      prompt fixed it; distinct pair heat_rate vs implied_heat_rate held (0 overlap); all source_refs +
      formulas preserved (deterministic). Learned: merge over-connects ~1/3 even w/ tight prompt; formula-
      aware judge caught 3/3 (real subtle over-reaches). DESIGN = Option A: judge is the guarantee, flagged
      objects reach production FLAGGED (Pass-2 architecture); B-line folded as flag-rate reducer (not a
      gate). ✔
- [ ] 3 — FULL SYNTHESIS (on go): all chapters + global pass. Resumable.
- [ ] 4 — STRUCTURE + OUTPUTS: energy_knowledge_base/ layout + taxonomy/concept_graph/contradictions. Counts
      reconcile; 5 random re-checked.
- [ ] 5 — REPORT PDF: canonical count, merge stats, top-10 by source breadth, contradictions, excluded count,
      honest caveat (queue open, Pass 5-6 + Co-Pilot NOT built).

## Append-only log
- setup (2026-08-21) — Pass 2 done (911 validated, 54 review queue open). Pass 3 = synthesis+dedup on the
  857 trusted. Architecture PDF read (7pg archetype). Next: build kb_synthesize.py grouping stage (T1, no
  LLM) + excluded_from_pass3.json, STOP for go.
