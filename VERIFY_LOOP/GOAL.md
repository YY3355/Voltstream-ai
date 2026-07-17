# GOAL — constraint arcs from MEASURED data (guardrail cleared: measured only, no estimated transfers)

constraint_arcs.py (in repo, fixture-tested): parse_constraints(NP6-86-CD df) -> binding+placeable
rows; match_stations(names, registry, min_score) -> (matches, unmatched); build_arcs(constraints,
registry) -> {arcs[], n_constraints, n_placed, match_rate_pct, unplaced[], unmatched_stations[],
labels{measured,partial,scope}}. RULE: an arc is drawn only if BOTH endpoints match a real
substation; unmatched are counted/listed, never guessed.

## HARD GATE (user directive)
Fetch a substation registry MYSELF (HIFLD primary, OSM fallback), cache it, and REPORT the real
match rate BEFORE building any UI. If match rate < 25%, STOP and show the unmatched list.

## Confirmed facts
- NP6-86-CD (ercot_archiver.fetch_constraints_query) returns fromStation/toStation/limit/value/
  ShadowPrice/from&toStationkV/violatedMW — all columns build_arcs needs. LATEST snapshot is often
  just 1-2 binding constraints, so measure the match rate over ALL distinct stations in binding
  constraints across a multi-day window (representative), not one instant.
- HIFLD Electric Substations (working): https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/
  services/Electric_Substations/FeatureServer/0 — 4,939 TX subs; fields NAME/LATITUDE/LONGITUDE/
  MAX_VOLT/COUNTY/STATUS. Many NAME='UNKNOWN######' (won't match ERCOT abbrevs). OSM/Overpass
  reachable with a User-Agent header.

## Tasks
- **T1** substation_registry.py: fetch HIFLD TX subs (paginated), normalize to name/lat/lon/kv/
  county/source, cache (gitignored). OSM/Overpass fallback/supplement if needed. Verify: registry
  has thousands of placeable rows.
- **T1-GATE** Pull binding constraints over a multi-day window, collect distinct stations, run
  match_stations vs the registry, REPORT match rate + unmatched list. If <25% STOP and show
  unmatched. (No UI before this passes.)
- **T2** (only if gate passes) /api/constraintarcs endpoint: live NP6-86-CD -> parse_constraints
  -> build_arcs(registry). Honest error/empty passthrough.
- **T3** (only if gate passes) Map arc layer + checkbox: deck.gl ArcLayer, width=utilization,
  color=shadow price; popup per arc (constraint, from/to, flow/limit, shadow $, contingency);
  show match rate + unplaced count. Labels verbatim from labels{}. MEASURED arcs only.
- **T4** Stop; measured only, no estimated transfers.

## Definition of done (through the gate)
- Registry cached with thousands of TX substations (name+coords).
- Real match rate reported against the true binding-constraint station universe.
- If >=25%: proceed to endpoint + map layer, verify arcs render, other layers/tabs untouched,
  push + redeploy. If <25%: STOP, present the unmatched list, await user decision.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER fabricate a coordinate — both-ends-or-no-arc. Registry cache gitignored; commit only a
  small summary if an endpoint needs it on Fly. No estimated/interpolated transfers, ever.
