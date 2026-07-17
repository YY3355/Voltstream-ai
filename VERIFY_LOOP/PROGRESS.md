# Progress — constraint-arc recovery (curated crosswalk before shelving)

Max 12 iterations. Supervised. GATE: complete arc-row placement >= 25% before any UI.

## Tasks
- [done] R1 — fetch_sced_window.py (277,574 rows/89d) + constraint_report.py. 89d: station 36.8%,
  arc-row 17.3%. Sole-blocker ranking: OLNEY 3799, SCRCV 2922, MDO 2856, MGSES 2067, VENSW 1710,
  BCKSW 1690, PALOUSE 1642... top 3 = +9,577 rows -> ~27% (clears 25% gate). commit ce35bd4.
- [doing] R2 — crosswalk.json + authoritative pre-match (precedence over fuzzy, provenance+conf).
- [todo] R3 — research+curate smallest top-N set (verified coords only); re-run gate per batch.
- [todo] UI — only if complete arc-row placement clears 25%.

## Log
- prior gate STOP: 33.1% station / 6.1% arc-row / 14.1% unique-constraint / 0 live arcs.
- registry = 9,472 subs (HIFLD 4,929 + OSM 4,543). Root cause: ERCOT codes (MGSES/ATSO/...) have
  no public code->name->coord table; need a curated crosswalk.
- 90d SCED constraint pull -> data_archive/constraints/sced_90d.pkl (background, gitignored).
