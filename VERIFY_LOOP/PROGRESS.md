# Progress — Map Phase 2 (weather layer)

Max 12 iterations. Supervised.

## Tasks
- [done] T1 — /api/weather endpoint + weather_data.py committed. Verified: fixture PASSES;
  /api/weather 200 (0.09s) 8 zones, signal light/7.6mph/48h 10.5/4 belt zones, caveat, 48h
  arrays. commit 05da5f1.
- [done] T2+T3+T4 — weather layer (temp fill/wind size/cyan wind-belt rings + mph labels),
  click popup (temp/wind/48h sparkline SVG/note/centroid caveat), wind-belt banner (state+
  now/48h+mechanism), honest labels (centroid + caveat verbatim). Verified CDP: toggle adds
  weather, Far West pickable+popup, banner+scope+legend correct; screenshot confirms. Other
  layers/tabs untouched (endpoints 200, quant renders). commit e0e3c03.
- [todo] DEPLOY — push, redeploy Fly (weather live there via Open-Meteo, no snapshot needed).

## Log
- init — API confirmed (run_weather, zone/signal shapes). Weather is LIVE (no key), self-caches
  30min -> works on Fly without a committed snapshot. Reuse Phase-1 Map REG/layer pattern.
