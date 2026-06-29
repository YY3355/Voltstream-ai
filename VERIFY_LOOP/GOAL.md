# Goal
Wire the existing risk_engine.py into the app as panel 10.

risk_engine.run_risk(data_dir) already works; returns:
  n_paths, mean_pnl, std_pnl, var95, es95, best, worst, sharpe_like,
  optionality_value, optionality_pct, vega, hist_counts, hist_edges,
  calib{kappa, sigma, jump_prob_pct, jump_mean}

## Definition of done
1. `/api/risk` endpoint in app.py calls run_risk(os.environ.get("ERCOT_DATA_DIR","data"))
   and returns its dict (wrapped in try/except like the other endpoints).
2. New dashboard panel 10 in dashboard_live.html, matching existing panel style:
   - leads with a P&L distribution histogram (hist_counts/hist_edges)
   - VaR95 and expected-shortfall (es95) numbers
   - mean/std/Sharpe-like
   - optionality row framed "long volatility · vega +$X/vol-unit"
     (note absolute optionality is modest on calm data)

## How to verify (every iteration)
This project runs in the `volt` conda env (NOT base). Always prefix with `conda run -n volt`.
Start server:
    ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
Then:
    curl --max-time 60 http://127.0.0.1:8020/api/risk   (FIRST call ~25s: runs Monte Carlo)
        -> confirm sane numbers (no error; var95/es95/mean_pnl/hist_counts present)
    render http://127.0.0.1:8020/ via headless Chrome -> confirm panel 10 populates
Fresh-eyes check where possible.

## Guardrails
- Supervised. Max 12 iterations.
- Never commit anything that fails the curl check.
- One task per commit.
