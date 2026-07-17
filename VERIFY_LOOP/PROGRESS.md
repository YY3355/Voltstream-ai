# Progress — constraint-arc recovery (curated crosswalk before shelving)

Max 12 iterations. Supervised. GATE: complete arc-row placement >= 25% before any UI.

## Tasks
- [done] R1 — fetch_sced_window.py (277,574 rows/89d) + constraint_report.py. 89d: station 36.8%,
  arc-row 17.3%. Sole-blocker ranking: OLNEY 3799, SCRCV 2922, MDO 2856, MGSES 2067, VENSW 1710,
  BCKSW 1690, PALOUSE 1642... top 3 = +9,577 rows -> ~27% (clears 25% gate). commit ce35bd4.
- [done] R2 — station_crosswalk.py (authoritative exact-match, provenance+conf). commit 9f01eb1.
- [done] R3 — 8 two-source-verified codes (MGSES/VENSW/DEVINESW/WHITE_PT/COLETO/TWINBU/FOWLRTON/
  BERGHE). GATE: arc-row 17.3%->25.0% CLEARED. But live UX sparse: median 1 arc/snapshot, 36%
  empty, latest=0. Bigger codes (OLNEY/SCRCV/MDO/PALOUSE/GANSO) NOT in public GIS by name -> not
  verifiable without ERCOT-internal docs; refused to guess. commit 9f01eb1.
- [decided] User: BUILD aggregate-first (90d binding-frequency arcs + live-now toggle + banner).
- [done] T2 — constraintarcs_run.py (49 arcs + 15 nodes + 149 resolved stations, 25KB) +
  /api/constraintarcs (aggregate default, live-now). Verified 200. commit 1ee5056.
- [done] T3+T4 — constraint-arc layer (49 arcs + 15 nodes, aggregate-first), live-now toggle
  (honest 0), banner (coverage + roadmap + scope), midpoint popups, measured-only. Verified CDP
  + screenshot; other layers/tabs untouched. commit 6861994.
- [done] DEPLOY — pushed (228451e..c9dbcd6) + Fly redeployed. Public /api/constraintarcs 200
  (49 arcs, 25% coverage, roadmap). Public CDP: toggle+banner+arclayer+nodes+popup+live-now(0)
  all pass, ok=true; live screenshot shows congested-grid arcs + banner. ALL DONE.

## Log
- prior gate STOP: 33.1% station / 6.1% arc-row / 14.1% unique-constraint / 0 live arcs.
- registry = 9,472 subs (HIFLD 4,929 + OSM 4,543). Root cause: ERCOT codes (MGSES/ATSO/...) have
  no public code->name->coord table; need a curated crosswalk.
- 90d SCED constraint pull -> data_archive/constraints/sced_90d.pkl (background, gitignored).
