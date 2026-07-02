# Goal
Wire dcopf.py into the app as panel 13 — "Toy DCOPF — Nodal Pricing & Congestion".
(dcopf.py copied in from ~/Downloads, same pattern as prior engines.)

dcopf.py (cvxpy+HIGHS, fast toy LP):
  solve_dcopf(wn_limit=None, wh_limit=None, load_scale=1.0, limit_scale=1.0) ->
    lmp: {WEST, NORTH, HOUSTON}
    decomp: {bus: {lmp, energy, congestion}}
    dispatch: {"WEST ($2)": mw, "NORTH ($35)": mw, "HOUSTON ($80)": mw}
    lines: [{line, flow, limit, binding, shadow_price}]
    total_cost
  sweep_transmission() -> [{scale, WEST, NORTH, HOUSTON, any_binding}]

## Definition of done
1. `/api/dcopf` endpoint in app.py returns (try/except like other routes):
   {"congested": solve_dcopf(),
    "uncongested": solve_dcopf(limit_scale=20.0),
    "sweep": sweep_transmission()}
2. Panel 13 in dashboard_live.html, house style, showing:
   - 3-bus LMP comparison, congested vs uncongested
   - LMP decomposition (energy + congestion per bus) with the BINDING line + its shadow price called out
   - transmission-sweep convergence chart (LMPs per bus vs scale, converging to one price)
   - clear label: a 3-bus LEARNING model with made-up costs; shows how LMPs & congestion
     fall out of the optimization; NOT calibrated to the real grid.

## How to verify (every iteration)
Project runs in `volt` conda env. Kill any stale :8020 listener first; wait for NEW instance
(200 on /openapi.json). Start server:
    ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
Then:
    curl --max-time 30 http://127.0.0.1:8020/api/dcopf
      -> sane: congested has price split (WEST<NORTH<=HOUSTON) + a binding line w/ shadow_price>0;
         uncongested is one price (all 3 equal); sweep converges to one price at high scale.
    Render http://127.0.0.1:8020/ via headless Chrome -> panel 13 populates.

## Guardrails
- Supervised. Max 10 iterations.
- Never commit anything that fails the curl check.
- One task per commit.
