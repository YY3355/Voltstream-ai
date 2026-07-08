# VoltStream

**An agentic co-pilot for ERCOT battery trading — built to learn the market by building it.**
*The math makes the decisions; the AI explains them.*

**▶ Live demo: https://voltstream-ercot.fly.dev**
*The DART tab pulls several days of live ERCOT data on first load and can take a couple of minutes; every other tab is instant.*

---

## The tour (six tabs)

**Co-Pilot** — the agentic brain: a router that sends each question to the right engine, RAG over ERCOT market notices with citations, and a confidence layer that auto-executes routine calls and escalates uncertain ones. The agent orchestrates and explains; it never overrides the optimizer.

**Asset Optimization** — Bolt, the MILP dispatch optimizer (cvxpy/HiGHS) under state-of-charge and backup-reserve constraints; energy + five-product ancillary co-optimization (RegUp, RegDown, RRS, ECRS, NonSpin) against one shared power budget, RTC+B-style; and a VPP fleet view aggregating heterogeneous batteries.

**Trading Desk** — a real-time decision engine (receding-horizon, no peeking: decides on forecasts, books actual prices, captures ~82% of the perfect-foresight ceiling); a live DART spreads & congestion monitor (DA vs RT across the four hubs, hour-of-day bias, hub basis); and the **paper book** — a DART strategy whose calls are git-committed *before* settlement, scored mechanically into an immutable ledger. The git history is the audit trail. First day has settled — a small paper loss; the disciplined record is the point, not the P&L.

**Quant & Structuring** — forward-curve construction (arbitrage-free block bootstrap, shaped to hourly from a real ERCOT hour-of-day profile; shaped hours re-aggregate exactly to block levels); fixed-for-floating swap mark-to-market; Monte-Carlo risk (mean-reverting jump-diffusion calibrated to real prices → P&L distribution, VaR/Expected Shortfall, and a positive vega — the battery is long volatility); and a QSE-loop analysis quantifying the cost of stale telemetry and MW/MWh mis-coordination.

**Learning Lab** — a 3-bus DCOPF (LMPs computed as genuine LP duals; congestion decomposition; the transmission sweep that converges to one price) sitting next to a **live binding-constraints monitor** reading today's actual SCED shadow prices from ERCOT's official API. The concept and the reality, side by side.

**About** — the honest-scope page. What's live, what's illustrative, what this is not.

## Data

- **Live:** DART panel (DA hourly + RT 15-min hub prices via gridstatus, no synthetic fallback); binding constraints (NP6-86-CD via the official ERCOT Public API); a rolling 30-day price store (per-day immutable cache, self-healing, cross-checked to the cent against an independent source) feeding every engine.
- **Archive layer:** ERCOT expires granular public reports after ~30 days, so VoltStream archives its own — plus a full ingest of ERCOT's product catalog (EMIL → SQLite) and a reusable official-API puller with a discovered query-endpoint fast path (30-day backfill in ~3 seconds instead of hours).

## Honest scope (the part that matters)

- **Not live trading.** No execution, fills, fees, credit, or risk limits; no certified market interface. The real-time engine demonstrates the *structure* of decision-making under uncertainty.
- **The paper book is a discipline record, not a profit claim.** Calls committed in advance, losses as auditable as wins.
- **Forward-curve levels are illustrative** (methodology is real; drop in CME settlements and it's market-calibrated). **No traded-options pricer on purpose** — pricing against an invented vol surface would be worse than not building it.
- **The toy DCOPF is a 3-bus learning model**; the constraints monitor reads what SCED computed — it is not a grid model (no topology, no shift factors).

## Stack

Python · FastAPI · cvxpy + HiGHS (MILP/LP) · scikit-learn (gradient-boosted quantile forecasting) · scipy · pandas/numpy · gridstatus + ERCOT Public API · SQLite · vanilla HTML/SVG dashboard.

## Run it

```bash
git clone <this repo> && cd voltstream-ai
pip install -r requirements.txt
ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean python -m uvicorn app:app --port 8020
# open http://127.0.0.1:8020
```

Offline mode (above) runs every engine on cached real ERCOT prices. For live mode, set ERCOT Public API credentials (`ERCOT_API_USERNAME`, `ERCOT_API_PASSWORD`, `ERCOT_API_SUBSCRIPTION_KEY`) in your environment and start without `ERCOT_LIVE=0`; first DART load fetches several days and takes a few minutes, then caches.

---

*Predecessor: VoltStream began as a multi-agent RL/forecasting experiment; this platform is its production-minded successor, narrowed to one market done honestly.*
