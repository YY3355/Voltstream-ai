# Progress

- [done]  T1: add `/api/dart` endpoint to app.py (+ commit dart_engine.py). LIVE check PASS.
- [done] T2: add DART panel 12 (#c-dart) + dart() renderer to dashboard_live.html
- [done] T3: final end-to-end verify (LIVE curl + headless-Chrome render)

## Log
- T1 finding: engine works + returns LIVE data, but run_dart(days=5) takes ~468s
  (RT_15_MIN ~55s/DAY via gridstatus doc-scraping; DA ~2.5s/day). Far over the 120s
  curl budget in the goal. Data is sane: 4 hubs, WEST-NORTH basis mean -11.31 (wind
  congestion), HOUSTON-NORTH +3.3, SOUTH-NORTH -2.25, window 143h. data_source LIVE.
  Plan: warm server cache via one long bg curl (~8min, acknowledged-slow first call),
  then official fast check + render hit the 30-min TTL cache. Endpoint keeps run_dart() default.
- T1 verified: warm curl http 200 in 434s, confirming curl 0.019s (cache). LIVE CHECK PASS
  (data_source LIVE, 4 hubs, basis 3 keys, series 72/72/72, hod 24, basis_series 72). commit 907e7d6.
- T2+T3 verified: headless-Chrome render of / (warm cache) shows panel 12 populated: hero
  HOUSTON +$0.72 / DA-rich 66.4% / 143h / 4 hubs; DA-vs-RT overlay + DART-spread + hour-of-day
  bias charts all present; basis strip WEST-NORTH -11.31 / HOUSTON-NORTH +3.30 / SOUTH-NORTH -2.25.
- Aside: header shows "backend offline" during headless render because /api/state (forecast GBM)
  is slow to first-paint; pre-existing, unrelated to DART panel.
