# Progress — wire price_store as the platform price source

- [blocked] T1: backfill ensure_days(30) in background; verify cached_days() ~30
- [done]  T2: wire ercot_live.get_prices() -> rolling store first (gate on LIVE_ON)
- [done]  T3: wire ercot_data.load_prices() -> store when PRICE_STORE!=0 AND ERCOT_LIVE!=0
- [done]  T4: extend app.py startup pre-warm to ensure_days(30)
- [done]  T5: final verify (MAIN recent target + all endpoints + tabs; REGRESSION ERCOT_LIVE=0 CSV)

## Notes
- dart_cache RT days now: 06-25..07-04 (10). Backfill target 30 = 06-05..07-04.
- load_prices consumers: cooptimize, copilot, forecast_engine, forward_curve, risk_engine,
  vpp, rt_engine, qse_loop (+ ercot_live fallback). get_prices consumers: app compute_state,
  api_cooptimize, api_vpp.
- Design: ERCOT_LIVE=0 = fully offline (CSV everywhere); PRICE_STORE=0 = disable store in
  load_prices only. fetch_missing=False in request paths (backfill/pre-warm populate cache).

## Log
(append: task, what verified, commit hash)

## Verify results
- T2/T3/T4 committed 0b24f09 / 2701d9a / 558c8a7.
- MAIN (no ERCOT_LIVE=0): /api/state 200, source="rolling store (10 cached days + today)",
  target_date 2026-07-04 (RECENT); all 12 endpoints 200; every tab renders.
- REGRESSION (ERCOT_LIVE=0): /api/state 200, source="cached ERCOT CSVs", target 2026-05-18;
  all endpoints 200; renders. CSV path unchanged.
- T1 BLOCKED (external): ensure_days(30) fetched 0 new — ERCOT MIS has expired the per-day
  RT_15_MIN docs older than ~06-25 (NoDataFoundException; doc ExpiredDate 2026-07-05). Store
  capped at the 10 recent days it already holds. Core goal still met (engines on current
  prices). Window self-heals toward 30 as new days accrue via the pre-warm maintenance.
