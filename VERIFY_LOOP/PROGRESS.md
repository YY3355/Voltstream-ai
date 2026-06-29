# Progress

- [done] T1: add `value_swap()` to forward_curve.py (MtM math)
- [done] T2: add `/api/swap` endpoint to app.py
- [done] T3: add swap panel (#c-swap) + swap() renderer to dashboard_live.html
- [done] T4: final end-to-end verify (curl + headless-Chrome page render)

## Log
- T1+T2: verified via curl in `volt` env. /api/swap defaults -> strike 28.55,
  avg 31.72, basis 3.17, mtm 139430.92 (10MW, 4392h). peak/strike40/25MW ->
  avg 35.46, mtm -237791.97. Sane + consistent. (commit pending below)
- Env note: server only boots under `conda run -n volt`; base env has cvxpy/numpy clash.
- T3+T4: verified in `volt`. curl /api/swap sane. Headless Chrome render of /
  shows panel 9 populated: +$139,431, strike $28.55, fwd avg $31.72, 10MW,
  4392h, 43,920 MWh, basis +$3.17/MWh; bar chart + legend present; no placeholder.
