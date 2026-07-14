# GOAL — add an interactive ERCOT DART Map tab to VoltStream

Interactive ERCOT DART map (Mapbox GL + deck.gl via CDN script tags, no build step — matches
the vanilla-HTML platform). map_data.py is in repo, fixture-tested.

## API
- `dart_engine.run_dart()` -> {stats{hub:{mean,hit_rate_pct,std,cum_1mw,n_hours}}, window,
  data_source, ...} or {error}
- `map_data.build_map(run_dart_result)` -> {center{lon,lat,zoom}, points[], window,
  data_source, note} (or {error, center, points:[]}). Each point: id/label/region/precision/
  lon/lat/dart/abs_dart/sign('rich'|'cheap')/hit_rate_pct/std/cum_1mw/n_hours.

## Tasks
- **T1** `/api/map` endpoint: call `dart_engine.run_dart()` then `map_data.build_map()`; return
  its dict, honest error passthrough if DART unavailable. Reuses DART's cache (fast once warm).
- **T2** Map tab in the nav: full-bleed dark Mapbox basemap centered on Texas (center from
  payload), deck.gl ScatterplotLayer over it — circle color green(rich)/red(cheap) by sign,
  radius by abs_dart, pickable tooltip (label, DART $, hit rate, precision note). Legend +
  data_source + window line. Mapbox public token from a JS const at top of the tab, clearly
  marked to replace (token supplied).
- **T3** Honest-scope line ON the map ("Hub markers are regional centers, not physical buses;
  a hub is an average of many nodes"), and lazy-load the tab (deck.gl/mapbox init only on first
  open, like the other heavy tabs via LOADERS/_loaded).

## Definition of done
- /api/map returns 200 with real points once DART is warm.
- Map tab renders: Mapbox dark basemap + deck.gl ScatterplotLayer circles, pickable tooltip,
  legend, honest-scope line, data_source/window line.
- Verified via headless Chrome: basemap + deck.gl canvas present, no JS errors, app-level
  success signal (map-meta populated) shows.
- Existing tabs untouched (curl the other endpoints + render another tab).
- Pushed when green; then REDEPLOY to Fly and confirm the public URL renders the map.

## Verification (CLAUDE.md recipe)
- `python map_data.py` fixture PASSES.
- Run app; warm /api/dart; curl /api/map -> 200 with points[] (or honest error if DART down).
- Headless Chrome /#map: `.mapboxgl-canvas` + deck canvas present, map-meta text populated,
  console error-free. Lazy-load: on `/`, map not initialized (no canvas) until tab opened.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER commit secrets/data caches. Mapbox token is a PUBLIC pk. token (URL-restricted by the
  user) — it lives in the client HTML by design (public token), not a secret to hide.
- Stay in scope: add the tab; do not refactor existing tabs.
