# Progress

- [done]  T1: add `/api/dart` endpoint to app.py (+ commit dart_engine.py). LIVE check PASS.
- [doing] T2: add DART panel 12 to dashboard_live.html (hero + 3 charts + basis strip), verify render
- [todo]  T3: final end-to-end verify (live curl + page render)

## Log
- T1 finding: engine works + returns LIVE data, but run_dart(days=5) takes ~468s
  (RT_15_MIN ~55s/DAY via gridstatus doc-scraping; DA ~2.5s/day). Far over the 120s
  curl budget in the goal. Data is sane: 4 hubs, WEST-NORTH basis mean -11.31 (wind
  congestion), HOUSTON-NORTH +3.3, SOUTH-NORTH -2.25, window 143h. data_source LIVE.
  Plan: warm server cache via one long bg curl (~8min, acknowledged-slow first call),
  then official fast check + render hit the 30-min TTL cache. Endpoint keeps run_dart() default.
