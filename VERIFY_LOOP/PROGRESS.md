# Progress — TRUE per-county weather + map layer fixes

Max 15 iterations. Supervised. Verify CDP + SCREENSHOTS. Implement order: T3 -> T1 -> T2 -> T4.

## Tasks
- [done] T3 — per-county Open-Meteo fetch (254 centroids, batched ~100/req) + county_weather
  consumes it directly (0 gray) + new label + wind_signal (83 wind-belt counties) from county data;
  /api/countyweather serves it. Fixtures pass. curl: 254 feats, 254 colored / 0 uncolored, label
  verbatim, wind_signal present, no zone field. Independent subagent REALNESS check: 91 distinct
  temps (not ~8), coherent S-hot/W-high-cool gradient, Dallas 99.5 vs Tarrant 96.6 (adjacent, not
  identical) — true per-county. countyheat sidebar intact (87). Also updated dashboard readers
  (countyWxTip, layerStat, caveat, toggle label) to the per-county shape. commit PENDING.
- [done] T1 — explicit Z_ORDER puts county fill at the BOTTOM (draw order == pick priority in deck);
  markers/arcs draw + pick above it. Real CDP pickObject at a battery's projected pixel (county
  fill ON) returns layer 'batteries' (pickedIsBattery true); pick stack [batteries, county, ...];
  county still pickable underneath (present in stack) for its own tooltip. commit PENDING.
- [todo] T2 — outlines always-on; fill is the toggle; DELETE zone-marker layer entirely; rewire
  wind-belt banner to county data.
- [todo] T4 — legend temp+rain w/ new label, remove weather legend entry; sidebar battery-MW untouched.
- [todo] DEPLOY — push, redeploy Fly.

## Log
- init — read weather_data.py, county_weather.py, app.py /api/countyweather, dashboard initMap
  (REG order, buildLayers, pop/pick, banner, legend). geojson: 254 Polygon feats NAME+FIPS, committed.
  Plan: T3 backend first (new shape: all colored + wind_signal), then UI (T1 order/pick, T2 outlines/
  delete-weather/rewire-banner, T4 legend). Verify pick via real deck.pickObject at projected pixel.
