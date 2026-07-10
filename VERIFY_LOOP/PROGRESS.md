# Progress — the Decade Study

- [doing] T1: reach test (query endpoint back to 2017?) + decade backfill
- [todo]  T2: assemble series + run study + cache result JSON (sanity: Uri 2021, coverage)
- [todo]  T3: /api/decade endpoint (serve cached JSON)
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
