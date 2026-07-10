# Goal
The Decade Study: multi-year battery revenue backtest on real ERCOT prices via decade_study.py.
API: run_backtest(prices, duration_h, rte, cycle_cap) -> daily df; yearly_summary(daily);
concentration_decade(daily) -> (pct, k); lever_sweep(prices, durations, cycle_caps);
forward_scenarios(annual_revs).

## Tasks
- T1 REACH TEST: probe how far back the NP6-905-CD query endpoint (spp_node_zone_hub) serves
  HB_HOUSTON — try 2017-01. If it reaches years -> backfill 2017..present via paginated query
  into data_archive/decade/{year}.pkl (gitignored). If it refuses old dates -> archive-doc path
  per year (throttled, background). REPORT which path won + how far real data actually goes.
- T2 RUN: assemble full HB_HOUSTON 15-min series; run study durations (1,2,4)h, rte 0.88,
  cycle caps (unlimited=None, 1.0/day); cache full result JSON to data_archive/decade_result.json
  (gitignored; minutes of compute, compute once). SANITY before trusting: 2021 shows Winter
  Storm Uri (Feb best-day, max prices in thousands, extreme top10 share); year coverage >=95% of
  days for included years (drop + report partial years).
- T3 ENDPOINT: /api/decade serving the cached JSON (yearly table, decade concentration, lever
  sweep, forward P10/50/90). Honest empty/rebuild note if cache missing.
- T4 PANEL in Quant & Structuring: year-by-year $/MW-year bars (Uri callout), concentration
  headline ("top 1% of days = X% of revenue"), duration x cycle lever table, forward P10/50/90
  with the assumption stated. Honest labels IN PANEL: perfect-foresight CEILING (good policy
  ~80%); energy arbitrage ONLY — AS excluded so AS-heavy recent years understated; nominal $;
  1 MW normalized.

## Verify (CLAUDE.md recipe)
- volt env; source ~/.zshenv (ERCOT creds for the query endpoint); ~/.fly for anything fly.
- T1: probe returns real 2017 rows OR documents refusal; decade cache years present.
- T2: sanity asserts (2021 Uri, coverage). result JSON written.
- T3: start server ERCOT_DATA_DIR=data_clean conda run -n volt uvicorn app:app :8020 (kill stale);
  curl /api/decade 200 with yearly/concentration/levers/forward. All existing endpoints still 200.
- T4: headless-Chrome render /#quant -> decade panel populates; Uri callout, honest labels present.

## Guardrails: supervised, max 15 iters, one task one commit. NEVER commit the decade cache
  (data_archive/ is gitignored — verify). decade_study.py commit with T1/T2.
