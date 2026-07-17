# Progress — constraint arcs (measured), registry + match-rate GATE

Max 12 iterations. Supervised. GATE: report match rate before UI; STOP if <25%.

## Tasks
- [done] T1 — substation_registry.py fetches+caches HIFLD (4,929) + OSM (4,543) = 9,472 TX subs
  (6,600 real names). Reusable, cached (gitignored). commit pending.
- [BLOCKED] T1-GATE — match rate over real binding-constraint stations (7d, 124 distinct):
  station match 33.1%, BUT arc placement (both-ends-or-no-arc, what actually draws) = 6.1% of
  rows / 14.1% of distinct constraints; the LIVE snapshot draws 0 arcs (1 binding, both ends
  unmatched). The map-relevant number is well under 25% -> STOP per directive. Root cause: ERCOT
  station codes (MGSES/ATSO/NLARSW/PDSES...) have no public crosswalk to HIFLD/OSM full names.
- [held] T2/T3/T4/DEPLOY — NOT started; await user go/no-go on the low-coverage finding.

## Log
- init — fixture PASSES. NP6-86-CD has all needed cols (fromStation/toStation/limit/value/...).
  Latest snapshot ~1 binding constraint -> measure match rate over a multi-day station universe.
  HIFLD endpoint found (4,939 TX subs, services5/HDRa0B57OVrv2E1q); many NAME=UNKNOWN. Overpass
  needs User-Agent.
