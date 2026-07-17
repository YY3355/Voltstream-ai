# GOAL — Phase 3: locational decade revenue with year playback on the Map tab

Delivers the public promise: "what a battery at this location would have earned, year by year,
on real history." locational_revenue.py in repo, fixture-tested.

## API
- `build_locational(prices_by_hub_dict, hub_coords_dict, duration_h=2.0)` -> {years[],
  frames{year:[{hub,lon,lat,rev,best_day,best_day_rev,max_price,top10_share_pct}]}, by_hub,
  mean_by_hub, rev_min, rev_max, dropped_partial_years, duration_h, labels{what,ceiling,
  regional,excludes,not_forecast}}. HUBS = HB_HOUSTON/NORTH/SOUTH/WEST.

## KEY DATA FACT (verified)
The cached data_archive/decade/*.pkl are SINGLE-HUB (HB_HOUSTON) Series. backfill_decade_hub
does NOT cache raw bundle zips. So the 4-hub extraction must RE-DOWNLOAD the monthly SPP
bundles (ercot_archiver.list_bundles + bundle_to_hub_series), parsing all 4 hubs per download
(network dominates). Cross-check: my Houston extraction must match the existing Houston pkl.

## Tasks
- **T1** DATA: locational_run.py — download each monthly bundle once, extract per-hub 15-min
  series for all 4 hubs (2018-2025), run build_locational with map_data.HUB_POINTS coords,
  cache result JSON. Compute once (minutes). Sanity: 2021 shows Uri at EVERY hub (max_price in
  thousands, extreme top10 share); report dropped partial years. Cross-check Houston vs cache.
- **T2** /api/locational serving the cached JSON; commit the small summary JSON (like
  decade_result.json) + .dockerignore un-exclude so it works on Fly.
- **T3** MAP: year slider (2018->2025) scrubbing frames; hub circles sized/colored by that
  year's $/MW-year on a FIXED scale (rev_min..rev_max) so years compare; play button animating
  years; popup per hub w/ that year's revenue, best day + $, max price, top-10 share. 2021 (Uri)
  must be visually dramatic.
- **T4** Labels verbatim from labels{}: ceiling not achievable; HUB-LEVEL regional not nodal;
  energy-only no AS/degradation/capex; history not forecast. NO animated power-flow arcs (no
  flow data, won't fake).

## Definition of done
- /api/locational 200: 8 years (2018-2025) x 4 hubs in frames; rev_min/rev_max; labels.
- 2021 sanity: every hub max_price in thousands + elevated top10 share.
- Map tab: slider scrubs frames, circles resize/recolor on fixed scale, play animates, hub
  popup shows year detail; 2021 spikes visibly.
- Honest labels verbatim on map. NO flow arcs.
- Other layers (hubs/batteries/plants/cities/weather/county) + other tabs untouched.
- Pushed when green; redeploy to Fly (summary JSON committed so it works there).

## Verification (CDP)
- locational_revenue.py fixture PASSES.
- locational_run.py produces JSON with 8 yrs x 4 hubs; Houston series == cached pkl (cross-check).
- curl /api/locational -> 200 shape + 2021 Uri sanity.
- CDP /#map: slider present, scrub year -> frame changes (circle radii change), 2021 max radius
  spike, play button advances, hub popup shows year detail; other layers still toggle; tabs render.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only.
- NEVER commit data caches/secrets (raw decade pkls, bundles stay out). Only the small
  locational_result.json summary is committed (like decade_result.json).
- Do not break Phase-1/2 layers, zoom, forecast, or other tabs. NO fabricated flow data.
