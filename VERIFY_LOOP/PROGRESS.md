# Progress — constraint-arc recovery (curated crosswalk before shelving)

Max 12 iterations. Supervised. GATE: complete arc-row placement >= 25% before any UI.

## Tasks
- [doing] R1 — constraint_report.py: 90d frequency-ranked unmatched-code report (7 fields) +
  alias candidates + est. coverage gain. (cache pull running in background.)
- [todo] R2 — crosswalk.json + authoritative pre-match (precedence over fuzzy, provenance+conf).
- [todo] R3 — research+curate smallest top-N set (verified coords only); re-run gate per batch.
- [todo] UI — only if complete arc-row placement clears 25%.

## Log
- prior gate STOP: 33.1% station / 6.1% arc-row / 14.1% unique-constraint / 0 live arcs.
- registry = 9,472 subs (HIFLD 4,929 + OSM 4,543). Root cause: ERCOT codes (MGSES/ATSO/...) have
  no public code->name->coord table; need a curated crosswalk.
- 90d SCED constraint pull -> data_archive/constraints/sced_90d.pkl (background, gitignored).
