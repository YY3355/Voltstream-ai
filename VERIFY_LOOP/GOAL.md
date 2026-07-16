# GOAL — Map architecture Phase 2: weather layer on the Map tab

weather_data.py in repo, fixture-tested. run_weather() -> {zones[], signal{...}, source, note}
or {error, zones:[]}. Self-caches 30min to data_archive/weather (gitignored). LIVE Open-Meteo
fetch, NO API KEY — so it works live on Fly with no committed snapshot (the box fetches fresh).

## API
- `run_weather(ttl_s=1800)` -> {zones[], signal, source, note}
- zone: zone/lat/lon/wind_heavy/note/precision('zone_centroid')/temp_f/wind_mph/
  forecast_hours[]/forecast_temp_f[]/forecast_wind_mph[] (up to 48h)
- signal: wind_belt_avg_mph, wind_belt_48h_avg_mph, state('strong'|'moderate'|'light'),
  mechanism, zones_counted[], caveat

## Tasks
- **T1** `/api/weather` endpoint calling run_weather() (self-caches 30min; honest error
  passthrough, mirror /api/dart).
- **T2** Weather layer + checkbox on the Map tab: 8 zone markers, color by temp_f (cool->hot
  ramp), wind indicator sized/labeled by wind_mph, wind-belt zones visually distinguished.
  Popup: zone, temp, wind, 48h wind trend sparkline if easy, zone note.
- **T3** Wind-belt banner on the Map tab: signal.state + signal.mechanism + 48h average — the
  market story in one line ("Wind belt: strong, 24 mph -> more wind generation -> lower net load").
- **T4** Honest labels: zone markers are REGIONAL CENTROIDS sampling a large zone (not a
  weather field); weather only, not a price forecast (signal.caveat verbatim).

## Definition of done
- /api/weather 200 with 8 zones + signal.
- Map tab: weather checkbox toggles the layer; 8 zone markers colored by temp + wind-sized,
  wind-belt distinguished; popup per zone; wind-belt banner shows state+mechanism+48h.
- Honest labels on map (centroid sample + caveat verbatim).
- Other layers (hubs/batteries/plants/cities) + other tabs untouched.
- Pushed when green; redeploy to Fly (weather is live there — no snapshot).

## Verification (CLAUDE.md recipe)
- weather_data.py fixture PASSES.
- Run app; curl /api/weather -> 200, 8 zones + signal.
- Headless Chrome / CDP /#map: toggle weather checkbox -> weather in active layer set + markers
  render; banner text shows state/mechanism/48h; a zone is pickable+popup renders; other layers
  still toggle; existing tabs render.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER commit data caches/secrets. data_archive/weather gitignored. No key involved.
- Do not break Phase-1 layers (hubs/batteries/plants/cities), zoom, or other tabs.
