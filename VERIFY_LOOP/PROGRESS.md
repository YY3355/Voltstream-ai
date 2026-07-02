# Progress

- [done]  T1: add `/api/dcopf` endpoint to app.py (+ commit dcopf.py)
- [doing] T2: add DCOPF panel 13 to dashboard_live.html (LMP compare + decomp + sweep), verify render
- [todo]  T3: final end-to-end verify (curl + page render)

## Log
- T1: verified in `volt`, /api/dcopf http 200 in 0.13s. Independent checks PASS: congested
  WEST 2 < NORTH 41 <= HOUSTON 80; binding line WEST-HOUSTON 100/100, shadow $117; decomp
  sums (WEST cong -39 / HOUSTON +39, energy 41); uncongested all 35; sweep -> 35 (any_binding
  false) at scale>=3. NB: binding line is WEST-HOUSTON (read from data, don't hardcode WEST-NORTH).
