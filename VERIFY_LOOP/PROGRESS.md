# Progress — the Decade Study

- [done]  T1: reach test (query endpoint back to 2017?) + decade backfill
- [done]  T2: assemble series + run study + cache result JSON (sanity: Uri 2021, coverage)
- [done]  T3: /api/decade endpoint (serve cached JSON)
- [todo]  T4: Quant panel (year bars + concentration + levers + forward, honest labels)

## Notes
- ercot_archiver has fetch_prices_query(days,...) (query artifact spp_node_zone_hub, deliveryDate
  range). Need a date-RANGE fetcher for per-year. data_archive/ gitignored -> decade cache safe.
- decade_study API confirmed. rte 0.88, durations (1,2,4), cycle_caps (None, 1.0).

## Log
- T1 REACH: query endpoint (spp_node_zone_hub) serves ONLY ~2024-01->present (0 for 2023 & older)
  -> NOT the decade. Archive-doc path = full history to 2016 but 96 docs/day (427,392 docs) =
  impractical. WINNER: the BUNDLE endpoint (/bundle/NP6-905-CD) -> 102 MONTHLY zips 2018-01 ->
  2026-06 (~8.5yr, includes Uri). One 13MB zip/month of ~2689 per-interval nested CSVs.
  Real data reaches 2018-01 (not 2017 — reported). bundle_to_hub_series verified on 2021-02:
  2688 pts, Uri Feb 13-19 maxing ~$9000, monthly mean $1516. Backfill running -> data_archive/decade/{year}.pkl.
- T1 DONE: decade cache 2018-2025 full (~35036 pts/yr) + partials (2017 junk, 2026 half). commit a22fa4e.
- T2 DONE: decade_run.py -> data_archive/decade_result.json (gitignored) in 49s. SANITY PASS:
  Uri 2021 best-day 2021-02-15 $30,944, maxP $9,161, top10 59.3%; coverage all included yrs >=95%
  (dropped 2017 junk + 2026 49.6%); concentration top1%=31% of decade rev; levers monotonic;
  forward P10/50/90 $939K/$1.17M/$1.41M. NEVER committed the cache (verified gitignored).
- T3 DONE: /api/decade serves cached JSON (200 @6ms, available, years 2018-2025, yearly+
  concentration+levers+forward+labels). Honest note if cache missing. Other endpoints 200
  (constraints 000 = its own cold today-fetch timeout, pre-existing, unrelated to decade).
