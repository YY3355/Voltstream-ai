# Progress

- [done]  T1: add `/api/risk` endpoint to app.py (+ commit risk_engine.py it depends on)
- [done] T2: add risk panel 10 (#c-risk) + risk() renderer to dashboard_live.html
- [done] T3: final end-to-end verify (curl warm + headless-Chrome render)

## Log
- T1: verified via curl in `volt` (had to kill a stale :8020 listener first, then
  wait for the new instance). /api/risk http=200 ~15s -> n_paths 150, mean_pnl 0.744,
  std 0.261, var95 -0.315, es95 -0.236, sharpe 2.85, optionality 0.001, vega 0.038,
  hist 22 counts sum 150 / 23 edges. Sane + consistent.
- T2+T3: verified in `volt`. Warmed /api/risk (http 200), then headless-Chrome
  render of / shows panel 10 populated: mean $0.74, Sharpe 2.85, VaR95 $-0.32,
  ES $-0.24, std/best/worst present; histogram SVG with red tail + VaR/ES/mean
  markers; optionality banner "long volatility · vega +$0.04/vol-unit". No placeholder.
- Note: must kill stale :8020 listener and wait for the NEW instance before curling.
