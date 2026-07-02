# Progress

- [done]  T1: add `/api/dcopf` endpoint to app.py (+ commit dcopf.py)
- [done] T2: add DCOPF panel 13 (#c-dcopf) + dcopf() renderer to dashboard_live.html
- [done] T3: final end-to-end verify (curl + headless-Chrome render)

## Log
- T1: verified in `volt`, /api/dcopf http 200 in 0.13s. Independent checks PASS: congested
  WEST 2 < NORTH 41 <= HOUSTON 80; binding line WEST-HOUSTON 100/100, shadow $117; decomp
  sums (WEST cong -39 / HOUSTON +39, energy 41); uncongested all 35; sweep -> 35 (any_binding
  false) at scale>=3. NB: binding line is WEST-HOUSTON (read from data, don't hardcode WEST-NORTH).
- T2+T3: verified in `volt`. /api/dcopf http 200 ~0.13s. Headless-Chrome render shows panel 13
  populated: hero spread $78 / one-price $35 / energy $41 / binding WEST-HOUSTON / shadow $117 /
  cost $12690; grouped LMP bars (congested vs uncongested), decomp bars + energy line, sweep
  convergence chart, WEST-HOUSTON binding callout, learning-model label. Fixed one hardcoded
  legend ("WEST-NORTH tight" -> dynamic "WEST-HOUSTON binding" from data) and re-verified.
