# Progress

- [done] T1: add `value_swap()` to forward_curve.py (MtM math)
- [done] T2: add `/api/swap` endpoint to app.py
- [doing] T3: add swap panel to dashboard_live.html, verify page renders
- [todo]  T4: final end-to-end verify (curl + page)

## Log
- T1+T2: verified via curl in `volt` env. /api/swap defaults -> strike 28.55,
  avg 31.72, basis 3.17, mtm 139430.92 (10MW, 4392h). peak/strike40/25MW ->
  avg 35.46, mtm -237791.97. Sane + consistent. (commit pending below)
- Env note: server only boots under `conda run -n volt`; base env has cvxpy/numpy clash.
