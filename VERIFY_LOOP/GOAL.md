# GOAL — wire hedge_study.py as the hedging layer on the Decade Study

Wire `hedge_study.py` (in repo, fixture-tested) into the platform as the hedging layer on
top of the Decade Study.

## API (hedge_study.py)
- `year_table(daily_revenue_df, prices_series, discharge_mwh_per_day)` -> per-year table
  (year, merchant_rev, realized_avg, hours)
- `run_hedge_sweep(yt, discharge_mwh_per_day, ratios, bias_pct)` -> (sweep_df, per-year detail dict, F0 strike proxy)
- `summarize(sweep)` -> {vol_reduction_pct, best_year_given_up, worst_year_change}

## Tasks
- **T1** Extend `decade_run.py` to ALSO persist the per-day revenue table + per-year realized
  average hub price (both computed internally). Regenerate the cached result. Set
  `discharge_mwh_per_day` from the backtest's ACTUAL average daily discharge for the 2h
  battery (not a guess) — requires exposing discharge from the dispatch.
- **T2** Run hedge sweep on the REAL eight years (ratios 0/0.25/0.5/0.75/1.0, bias 0).
  Sanity: hedging must cap 2021 (Uri) hedged < merchant; report where the min-variance ratio
  lands. Cache result JSON; commit the small summary like the decade JSON.
- **T3** `/api/hedge` endpoint serving it.
- **T4** Panel in Quant & Structuring beside the decade panel:
  - ratio-vs-volatility curve (mark interior minimum)
  - per-year merchant-vs-hedged bars (Uri capped, calm years lifted)
  - takeaway "a flat swap hedges the level, not the tails — the residual is why structured products exist"
  - HONEST LABELS in-panel: strike is a stated proxy (across-years mean of realized averages
    — no public decade of futures marks), zero-expected-P&L by construction, perfect-foresight
    merchant underneath, energy-only, analysis not advice.

## Definition of done
- decade_result.json regenerated with per-year realized_avg + actual discharge_mwh_per_day.
- hedge_result.json computed on real 8 years, Uri capped, committed (small summary).
- /api/hedge returns the cached JSON.
- Quant tab renders the hedge panel (curve + bars + takeaway + honest labels) — verified via
  headless Chrome DOM/screenshot per CLAUDE.md recipe.
- decade_study.py fixture self-test still PASSES after the discharge change.
- Pushed when green.

## Verification (CLAUDE.md recipe)
- `python decade_study.py` fixture self-test PASSES.
- `python hedge_study.py` fixture self-test PASSES.
- Run app (uvicorn app:app), curl /api/decade + /api/hedge -> 200 with expected keys.
- Headless Chrome: load /#quant, confirm hedge panel DOM nodes + screenshot render.

## Guardrails
- Max 12 iterations. Supervised (check in per task). One task = one commit. Green commits only.
- NEVER commit data caches or secrets. decade_daily.pkl / raw price cache stay gitignored.
  Only the small hedge_result.json summary is committed (like decade_result.json).
- Do not break the decade_study fixture (backward-compatible discharge change only).
