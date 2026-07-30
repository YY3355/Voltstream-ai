# GOAL — Bolt dispatch chart: one focal point, visible price→dispatch causality, honest uncertainty

Redesign the Asset Optimization Bolt chart so it has ONE focal point (bars + SoC hero), makes the
price→dispatch causality visible, and shows an HONEST model uncertainty band. Scope: **Asset
Optimization tab only** — `dispatchSVG` / `dpTip` / `dp-kpi` + its CSS — plus Task 0 (research-note
correction) and final docs. **NO other tabs, NO map, NO signal.py, NO deploy.** Max 12 iterations,
ONE task = ONE commit, pause + report each task. Never commit red; same check red 3× = blocked, stop.

## HARD CONSTRAINTS (violating any = RED)
1. Every rendered number comes from solution arrays, model artifacts, or computed baselines — never
   hardcoded, never generative text. Templated strings only.
2. Confidence band = REAL MODEL OUTPUT ONLY: RT quantiles `RT_q = DA − DART_q` from the research
   model's committed artifacts (conformal-adjusted, `research/dart_forecast/`). Label verbatim:
   **"forecast band — research model vX · plan solves on point price"**. If artifacts are
   missing/stale for the plan's date, the band is **ABSENT** — never interpolated, never faked.
   Settled-actual RT renders gray ONLY where realized data exists.
3. "Now" marker renders ONLY when `plan_date == today` (local); else a quiet badge
   **"historical plan — <date>"**. Never manufacture liveness.
4. Motion: ENTRANCE-ONLY (bars grow, price line draws, SoC eases ≤1s), no ambient loops, no per-frame
   full re-renders (the T4 refreshLayers lesson); prefer CSS/SVG transitions; respect
   `prefers-reduced-motion`. Liveliness is NOT green from headless alone — final motion sign-off is
   Mike in a real browser (standing rule).
5. Honesty labels, units, and gross-only KPI caveats survive every restyle. Deploy needs Mike's
   explicit go, never the loop's.

## VERIFICATION (maker ≠ checker, fresh-eyes subagent per task)
Screenshot per task; the checker describes the chart COLD — hierarchy claims must appear in its
UNPROMPTED description ("bars and SoC dominate", not prompted agreement). Data checks: one band
quantile point re-derived from the model JSON by hand; one heuristic-capture number recomputed
independently; one action-card string traced to its source arrays.

## TASKS
0. Research-note correction (separate commit, research/ scope): did the locational/ repoint + N/S/W
   re-run happen? If yes → fix NOTE §9 stale claim + explain the n change. If no → apply the repoint
   (Houston byte-identical check), re-run N/S/W baselines through the unchanged harness, update JSONs+note.
1. Focal hierarchy: bars + SoC = hero (contrast up, SoC 2px); price/grid/KPI/floor recede; reserve
   zone ≤8% opacity (line + tag carry it).
2. Price→dispatch causality: faint vertical guides through charge/discharge windows across both
   panels; dispatch windows softly highlighted on the price panel. Guides ≤ hero contrast.
3. Annotations integrated: dense labels → hover; ≤2 pinned callouts, edge-anchored, never over bars.
4. Now/historical honesty (constraint 3): today-fixture → marker; 2026-05-18 → badge, no marker.
5. Heuristic baseline: naive TOU one-cycle dispatch (rules in comments); KPI = context triple
   "capture X% · heuristic Y% · PF 100%", all computed per plan.
6. Action card: one templated sentence from solution arrays only; optional "P(RT>$100) tonight: Z%"
   from the spike head IF band present. No forecast verbs — state numbers, not intentions.
7. Confidence band + settled-actual (constraint 2): soft band q10–q90 (q25–q75 inner), settled gray
   line, legend + verbatim label; band ABSENT (not faked) when no artifact.
8. Entrance motion (constraint 4): bars grow, line draws, SoC eases; stagger ≤1s; reduced-motion
   honored; flag for Mike's real-browser gate.
9. Rest-state + responsive audit: calm default, one focal point, no overlaps at 3 widths; caveats
   present; cold checker verdict "clear, decision-grade" in its own words.
10. Docs: CLAUDE.md explicit-go deploy rule + container-runtime gap; PROGRESS.md final state.

Env: `conda run -n volt`, `ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean`, kill stale :8020, warm endpoints,
headless screenshots per task. When all green: STOP with screenshots + real-browser checklist for Mike.
Promotion of the band's model into the live optimizer is a FUTURE decision.
