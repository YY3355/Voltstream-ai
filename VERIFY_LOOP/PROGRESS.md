# Progress — Phase 2 FINAL (county heat + day-ahead forecast)

Max 12 iterations. Supervised.

## Tasks
- [done] T1 — /api/countyheat + /api/forecast + map_layers.py. Verified: fixture PASSES;
  countyheat 200 (87 counties, 16,316.8 MW, Brazoria top); forecast 200 HOUSTON/WEST/NORTH
  (96 pts, ordered quantiles, caveat). commit dcc379a.
- [done] T2+T3 — county heat layer + ranked 87-county panel + hub-popup forecast fan. Verified
  CDP: panel 87 rows, county toggle+pickable, hub fan SVG + caveat verbatim, scope rollup/mean-
  position/no-heatmap; screenshot confirms. Other layers/tabs untouched. commit f471224.
- [done] T4 — STOP: no transmission/constraint mapping added. Phase 2 stands here.
- [todo] DEPLOY — push, redeploy Fly (forecast may honest-error if the store is thin there).

## Log
- init — API confirmed. get_prices_rolling returns (series, meta) TUPLE; use include_today=False
  + fetch_missing=False for a fast forecast endpoint (cached history only). 4 hubs supported.
  forecast_hub RAISES on <960 rows -> honest passthrough. Reuse Map REG/pop pattern.
