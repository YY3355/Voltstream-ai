# Goal
Add a fixed-for-floating power swap valuation on top of forward_curve.py.

## Definition of done
1. `/api/swap` endpoint returns the swap's mark-to-market = (difference between a
   fixed strike price and the forward curve's average over a chosen period) × volume.
   Returns sane numbers.
2. A new dashboard panel in dashboard_live.html renders the swap MtM.

## How to verify (every iteration)
This project runs in the `volt` conda env (NOT base). Always prefix with `conda run -n volt`.
Start server:
    ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
Then:
    curl http://127.0.0.1:8020/api/swap   -> confirm sane numbers (no error, mtm/avg/strike present)
    load http://127.0.0.1:8020/           -> confirm the swap panel renders
Fresh-eyes check via subagent where possible.

## Guardrails
- Supervised. Max 12 iterations.
- Never commit anything that fails the curl check.
- One task per commit.
