# GOAL — Map architecture Phase 1: geography layers + layer controls + fix zoom

geo_data.py in repo (fixture-tested): load_geo() -> (batteries, plants, cities) DataFrames
with lat/lon/mw/county/operator/precision; county_rollup(df) -> per-county totals.
cities_table() = 28 embedded TX cities (always available). batteries/plants come from the EIA
860M fetch -> data_archive/geo/*.pkl.

## PREREQUISITE BLOCKER (external)
The EIA API key (845759783...d075) returns 403 API_KEY_INVALID on a clean direct call — so
`geo_data.py fetch` cannot populate batteries.pkl / plants.pkl yet. Consequences:
- Cities layer: fully real (28 embedded). DART hubs: already live.
- Batteries/Plants: share the cities code path; will light up automatically once a VALID key
  produces the cache. For layer-mechanics verification I may seed a SMALL fixture-shaped cache
  (parse_eia on the module's fixture rows) — clearly a stand-in, NOT committed (data_archive is
  gitignored) — then confirm real EIA data pending a working key.

## Tasks
- **T1** FIX ZOOM/PAN on Map tab: scroll-zoom, drag-pan, NavigationControl must work. Cause:
  deck MapboxOverlay(interleaved:false) overlay canvas intercepts events. Fix: interleaved:true
  (deck draws into mapbox context) + add NavigationControl. Verify programmatically: dispatch a
  wheel event over the map, map.getZoom() changes; scrollZoom/dragPan enabled; nav buttons exist.
- **T2** /api/geo endpoint: cached geography as layer-ready JSON — batteries (id/name/operator/
  mw/county/lat/lon), plants (+tech), cities (name/county/population/lat/lon), county_rollup for
  batteries. Honest empty-state if cache missing (tell user to run `geo_data.py fetch`).
- **T3** LAYER CONTROLS on Map tab: checkboxes toggling deck layers — DART hubs (existing),
  Batteries (size by MW, distinct color), Power plants (color by tech), Cities (size by
  population). Click popups: battery -> name/operator/MW/county; plant -> + tech; city ->
  population.
- **T4** Honest labels ON the map: battery/plant markers are EIA-reported asset coords (exact);
  city markers are centroids, NOT load-delivery points; data-center & city-level-load layers
  deliberately absent (no authoritative public data).

## Definition of done
- /api/geo 200 with real counts (cities real now; batteries/plants real once key works — else
  honest empty-state, verified).
- Map tab: zoom/pan/NavigationControl work; layer checkboxes toggle each layer; markers appear
  (cities real; batteries/plants via cache); popups per spec; honest labels on map.
- Existing tabs untouched. Pushed when green; redeploy to Fly.

## Verification (CLAUDE.md recipe)
- geo_data.py fixture PASSES.
- Run app; curl /api/geo -> 200 with counts (cities>=28; batteries/plants real or honest empty).
- Headless Chrome /#map: wheel event -> getZoom changes; nav buttons present; toggle each layer
  checkbox -> deck layer count changes / markers render; existing tabs render.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER commit data caches or secrets. data_archive/geo/*.pkl gitignored. EIA key stays in
  ~/.zshenv, never echoed/committed. Mapbox pk. token already in client HTML by design.
- Do not break the existing DART-hub layer or other tabs.
