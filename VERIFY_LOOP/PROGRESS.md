# Progress — KB Pass 3: chapter synthesis + global dedup

Supervised. Max 10 iters. ONE task = ONE commit. Verify fresh-eyes. Never commit red; same check ×3 = stop.
Pause for Mike's go at every STOP. Merge=combine-only (never invent). Judge/merge engine=claude-cli. No app.py.

## Input contract
857 TRUSTED (det-pass or SUPPORTED) synthesized; 54 EXCLUDED (47 UNSUPPORTED + 7 UNCLEAR) -> not deleted,
listed in excluded_from_pass3.json. Recomputed from _validation each run (re-runnable when queue clears).

## Checklist
- [x] 0 — Read KB_LOOP_RECIPE.md + loop-architecture PDF (archetype: synthesis loop, HEAT RATE dedup,
      non-negotiables, final /energy_knowledge_base layout). Trusted/excluded split = 857/54. GOAL/PROGRESS. ✔
- [ ] 1 — DESIGN + DRY GROUPING (no LLM): kb_synthesize.py grouping stage; normalize topics; merge_plan.json
      + summary (857 -> N canonical, top-10 groups). Verify 5 groups no-false-merge. ⏸ STOP.
- [ ] 2 — PILOT MERGE (claude -p) Part 4 (ch16-25). Marker-verify 5 canonical objects (provenance, no new
      material, ≥1 distinct pair unmerged). Contradictions. ⏸ STOP.
- [ ] 3 — FULL SYNTHESIS (on go): all chapters + global pass. Resumable.
- [ ] 4 — STRUCTURE + OUTPUTS: energy_knowledge_base/ layout + taxonomy/concept_graph/contradictions. Counts
      reconcile; 5 random re-checked.
- [ ] 5 — REPORT PDF: canonical count, merge stats, top-10 by source breadth, contradictions, excluded count,
      honest caveat (queue open, Pass 5-6 + Co-Pilot NOT built).

## Append-only log
- setup (2026-08-21) — Pass 2 done (911 validated, 54 review queue open). Pass 3 = synthesis+dedup on the
  857 trusted. Architecture PDF read (7pg archetype). Next: build kb_synthesize.py grouping stage (T1, no
  LLM) + excluded_from_pass3.json, STOP for go.
