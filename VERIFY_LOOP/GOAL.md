# GOAL — TRUE per-county weather + map layer fixes (ordering/picking, outlines-always, delete zone markers)

Three map fixes. County weather stops being zone-inheritance (8 readings tiled over counties) and
becomes REAL per-county readings (254 centroids). County polygons stop swallowing marker/arc picks.
Outlines become permanent basemap geography; the weather FILL is the toggle. The old 8-zone weather
marker layer is deleted; the wind-belt banner survives but recomputes from the new county data.

## Current state (pre-loop)
- weather_data.py: 8 ERCOT zone centroids; parse_openmeteo (current temp+wind+precip, 48h hourly);
  wind_signal (mean wind of 4 wind_heavy zones + 48h). run_weather() 30-min cache.
- county_weather.py: COUNTY_ZONE (198 counties -> 8 zones, 56 left out); build_county_weather joins
  ZONE weather to counties (gray where unassigned). temp_color(f)->[r,g,b].
- app.py /api/countyweather: run_weather -> build_county_weather -> merge into tx_counties.geojson
  (254 feats, 198 colored / 56 null-fill). coverage + uncolored list.
- dashboard_live.html map (initMap): REG layer registry order = hubs,batteries,plants,cities,county,
  weather,locational,constraints (array order == z-order; LATER renders ON TOP + wins picks). county
  = GeoJsonLayer(fill+outline, on:true) — currently ABOVE the marker layers (BUG: swallows picks).
  weather = ScatterplotLayer(wxZones)+TextLayer(labels), on:false. Wind-belt banner (#map-wxbanner)
  reads wx.signal. Legend @~1850 has a weather entry + county entry. Sidebar #county-panel = battery
  MW (separate /api/countyheat — DO NOT TOUCH). tx_counties.geojson: 254 feats, props NAME+FIPS,
  Polygon geom, committed under data_archive/geo/.

## Tasks (commit each; implement in dependency order T3 -> T1 -> T2 -> T4)
- **T3 PER-COUNTY WEATHER (backend first — everything downstream depends on the new shape)**:
  weather_data.py — add county-centroid fetch: centroids from cached tx_counties.geojson, Open-Meteo
  MULTI-LOCATION batching (~100 coords/req -> ~3 reqs), current temp+wind+precip, 30-min cache
  (data_archive/weather/counties.json). Pure parse fn + fixture. county_weather.py — new build that
  consumes per-county readings DIRECTLY: every county gets its OWN temp/wind/precip/fill; NO zone
  inheritance, NO gray unassigned. New label verbatim: "county-centroid readings — one real
  measurement per county; weather varies within large counties." Also compute a wind-belt summary
  (mean wind of the wind-belt-region counties) for the banner. /api/countyweather serves it: 254
  feats ALL fill!=null, coverage colored=254 uncolored=0, label, wind_signal.
  Verify: fixtures pass; curl 254 feats, 0 null fill, label present, wind_signal present.
- **T1 ORDERING + PICKING**: county fill renders UNDER every marker/arc layer (move to bottom of the
  deck layer array) so a battery/plant/hub/arc under a county polygon still wins hover/click. County
  stays pickable for its OWN tooltip only when the fill is active. Verify: with fill ON, a real pick
  at a battery's projected pixel returns layer id 'batteries' (not 'county'); with fill OFF county
  isn't pickable.
- **T2 OUTLINES ALWAYS + FILL TOGGLE + DELETE ZONE MARKERS + REWIRE BANNER**: county OUTLINES (thin,
  subtle) always render (permanent geography, not user-toggleable / always-on). The weather FILL is
  the toggle. DELETE the 8-zone weather layer entirely — ScatterplotLayer+TextLayer, its REG entry,
  its checkbox/toggle, its legend entry, its caveat, maxWind. KEEP the wind-belt banner — rewire it
  to cw.wind_signal (mean wind of wind-belt-region counties). Verify: no 'weather'/'weather-labels'
  deck layer + no weather checkbox; outlines visible with fill OFF; banner still populated + live.
- **T4 LEGEND/SIDEBAR**: legend = temp ramp + rain swatch with the new per-county label; remove the
  weather legend entry. Sidebar Battery-MW bar (#county-panel / allCounties) untouched. Verify:
  legend text = new label, no weather swatch; #county-panel rows identical.

## Definition of done
- /api/countyweather 200: 254 features, ALL colored from real per-county readings (0 gray), label =
  "county-centroid readings — one real measurement per county; weather varies within large counties."
- Map: batteries/plants/hubs/arcs pickable THROUGH the county fill; county outlines always visible;
  fill is one toggle; zone-marker layer + toggle + legend entry GONE; wind-belt banner live from
  county data. Legend temp+rain w/ new label. Sidebar battery-MW bar identical. Other tabs untouched.
- Pushed when green; redeploy Fly.

## Verify (CDP + SCREENSHOTS — visual)
- python weather_data.py / county_weather.py fixtures pass. curl /api/countyweather -> 254 feats,
  0 null-fill, label+wind_signal present. Independent (subagent) recount.
- CDP /#map: real pickObject at a battery pixel with county fill on -> 'batteries'; deck layers list
  has NO 'weather'/'weather-labels'; county-outline present with fill toggled off; banner text present.
- Screenshots: fill ON (all 254 shaded, no gray), fill OFF (outlines-only geography). Other tabs render.

## Guardrails
- Max 15 iterations. Supervised. One task = one commit. Green commits only.
- Per-county weather is REAL (one Open-Meteo reading per county centroid) — honestly labeled that a
  single centroid reading doesn't resolve within-county variation. No fabrication. Do NOT touch the
  sidebar battery-MW bar (#county-panel) or /api/countyheat. Keep /api/weather endpoint (other tabs).
