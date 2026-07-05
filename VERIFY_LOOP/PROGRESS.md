# Progress — wire price_store as the platform price source

- [blocked] T1: backfill ensure_days(30) in background; verify cached_days() ~30
- [done]  T2: wire ercot_live.get_prices() -> rolling store first (gate on LIVE_ON)
- [done]  T3: wire ercot_data.load_prices() -> store when PRICE_STORE!=0 AND ERCOT_LIVE!=0
- [done]  T4: extend app.py startup pre-warm to ensure_days(30)
- [todo]  T5: final verify (MAIN recent target + all endpoints + tabs; REGRESSION ERCOT_LIVE=0 CSV)

## Notes
- dart_cache RT days now: 06-25..07-04 (10). Backfill target 30 = 06-05..07-04.
- load_prices consumers: cooptimize, copilot, forecast_engine, forward_curve, risk_engine,
  vpp, rt_engine, qse_loop (+ ercot_live fallback). get_prices consumers: app compute_state,
  api_cooptimize, api_vpp.
- Design: ERCOT_LIVE=0 = fully offline (CSV everywhere); PRICE_STORE=0 = disable store in
  load_prices only. fetch_missing=False in request paths (backfill/pre-warm populate cache).

## Log
(append: task, what verified, commit hash)
