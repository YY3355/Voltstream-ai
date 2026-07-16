# GOAL — Phase 2 FINAL: county heat + day-ahead forecast on the Map tab

map_layers.py in repo, fixture-tested. Then Phase 2 STANDS (no transmission/constraint mapping).

## API
- `county_heat(batteries_df, top_n=25)` -> {counties[](top25), all_counties[], n_counties,
  total_mw, top_share_pct, note}. Row: county/mw/assets/lat/lon/share_pct.
- `forecast_hub(prices_series, horizon=96, min_train=960)` -> {times[], p10[], p50[], p90[],
  train_rows, history_end, model, caveat}. RAISES RuntimeError on thin history — SURFACE it,
  do not swallow/fake.
- Supporting: geo_data.load_geo() -> (batteries, plants, cities). price_store.get_prices_rolling(
  hub, days=30, include_today, fetch_missing) -> (series, meta) TUPLE. HUBS = HB_HOUSTON/NORTH/
  SOUTH/WEST.

## Tasks
- **T1** `/api/countyheat`: load_geo() batteries -> county_heat(). `/api/forecast?hub=HB_HOUSTON`:
  get_prices_rolling(hub, days=30, include_today=False, fetch_missing=False) -> (s,_meta) ->
  forecast_hub(s); per-hub ~30min cache; honest error passthrough if store thin (Fly box may be).
- **T2** County heat layer + checkbox: deck markers at county points sized/colored by MW +
  ranked county list panel BESIDE the map (county / MW / assets / share%). Honest label: rollup
  of real EIA assets; county points are the MEAN position of that county's assets, NOT
  boundaries; and NO price heatmap (4 hub prices can't honestly paint a surface).
- **T3** Forecast chart in each HUB popup: next-24h P10/P50/P90 fan (inline SVG, house style),
  fetched async on hub click, with model + caveat verbatim — a DAY-AHEAD model, separate from
  the platform's nowcaster, weaker by design.
- **T4** STOP: no transmission/constraint mapping. Phase 2 stands here.

## Definition of done
- /api/countyheat 200: ~87 counties / 16,317 MW total.
- /api/forecast?hub=HB_HOUSTON 200: 96 points, ordered quantiles (p10<=p50<=p90), model+caveat.
  (Honest error if the store is thin — that's acceptable, not a failure.)
- Map tab: county checkbox toggles the layer; county markers render; ranked county list panel
  populated; hub popup shows the forecast fan chart. Honest labels present.
- Other layers (hubs/batteries/plants/cities/weather) + other tabs untouched.
- Pushed when green; redeploy to Fly (forecast may honest-error on Fly if the store is thin).

## Verification (CLAUDE.md recipe / CDP)
- map_layers.py fixture PASSES.
- curl /api/countyheat -> 200 counts; curl /api/forecast?hub=HB_HOUSTON -> 200 ordered quantiles.
- CDP /#map: toggle county checkbox -> 'county' active + markers; county-panel list populated;
  click a hub -> popup fan SVG appears (async) with caveat; other layers still toggle; tabs render.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER commit data caches/secrets. Do not break Phase-1/weather layers, zoom, or other tabs.
- forecast_hub RAISES on thin history: surface the error honestly, never fabricate a forecast.
