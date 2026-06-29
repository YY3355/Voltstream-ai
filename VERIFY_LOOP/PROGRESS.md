# Progress

- [done]  T1: add `/api/risk` endpoint to app.py (+ commit risk_engine.py it depends on)
- [doing] T2: add risk panel 10 to dashboard_live.html, verify page renders
- [todo]  T3: final end-to-end verify (curl + page render)

## Log
- T1: verified via curl in `volt` (had to kill a stale :8020 listener first, then
  wait for the new instance). /api/risk http=200 ~15s -> n_paths 150, mean_pnl 0.744,
  std 0.261, var95 -0.315, es95 -0.236, sharpe 2.85, optionality 0.001, vega 0.038,
  hist 22 counts sum 150 / 23 edges. Sane + consistent.
