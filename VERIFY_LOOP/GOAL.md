# Goal
Wire qse_loop.py into the app as panel 11 (copied in from ~/Downloads, same pattern as risk_engine).

run_qse(data_dir) already works; returns:
  lag_curve: list of {lag_min, commit_err_mwh, revenue, pct_of_fresh}
  commit_err_2h, coupled_spike, power_spike, coord_gain_pct,
  coupled_rev, power_only_rev, n_paths, calib_jump_pct,
  illustration: {price[], soc_coupled[], soc_power_only[], capacity_kwh, reserve_kwh}

## Definition of done
1. `/api/qse` endpoint in app.py calls run_qse(os.environ.get("ERCOT_DATA_DIR","data"))
   and returns its dict (try/except like the other engine routes).
2. New dashboard panel 11 in dashboard_live.html, matching existing panel style, with TWO charts:
   - commitment-error-vs-telemetry-age curve (lag_curve: commit_err_mwh vs lag_min)
   - coordination illustration: price + the two SoC traces (soc_coupled, soc_power_only)
   Frame it as engaging Habitat's QSE article; note it models the CONCEPT with simulated
   telemetry, NOT a real QSE.

## How to verify (every iteration)
This project runs in the `volt` conda env (NOT base). Always prefix with `conda run -n volt`.
IMPORTANT: kill any stale :8020 listener first, then wait for the NEW instance (200 on /api/state).
Start server:
    ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
Then:
    curl --max-time 30 http://127.0.0.1:8020/api/qse   (first call runs Monte Carlo, ~25-30s)
        -> confirm sane numbers (no error; lag_curve / coord_gain_pct / illustration present)
    render http://127.0.0.1:8020/ via headless Chrome -> confirm panel 11 populates
    (warm /api/qse with curl FIRST so the page render returns from cache fast)

## Guardrails
- Supervised. Max 12 iterations.
- Never commit anything that fails the curl check.
- One task per commit.
