# Sign + alignment mapping (Task 2 — the gate that blocks scoring)

**PROVEN:  `dart = DA − RT = −(their "spread")`.**  Their P10/P50/P90 on *spread* map to dart as
**`dart ∈ [−P90, −P10]` (the 80% interval), median `−P50`.**  Reproduce: `python research/kardashev_eval/sign_gate.py` (exit 0).

## Evidence (frozen snapshot vs OUR raw prices)
`sign_gate.py` reconstructed **26 delivery hours across 3 days** (2026-07-15, -20, -26), HB_HOUSTON,
model tft-v2, from OUR stores and compared to their published `da` + `spread`:

- **max |our_DA − their_da| = 0.0000** → timezone + hour convention pinned.
- **max |our_dart − (−their_spread)| = 0.0000** → sign confirmed to the cent, every hour.

Sample (full table in the script output):

| ts (UTC hour-start) | their_da | our_DA | their_spread | our_dart (DA−RT) | −their_spread |
|---|---|---|---|---|---|
| 2026-07-15T20:00Z | 24.03 | 24.03 | −1.300 | +1.300 | +1.300 |
| 2026-07-20T23:00Z | 37.33 | 37.33 | +11.550 | −11.550 | −11.550 |
| 2026-07-26T23:00Z | 35.46 | 35.46 | −2.000 | +2.000 | +2.000 |

## Timezone + hour convention (pinned)
- Their `ts` is a **UTC hour-START**. CDT = UTC−5 for the entire window (July–Aug, no DST transition).
- OUR **DA** (`dart_cache/DAY_AHEAD_HOURLY`, gridstatus): `Interval Start` is tz-aware **CDT, hour-beginning**;
  `Interval Start → UTC == their ts`.
- OUR **RT** (`archive_cache/NP6-905-CD`, ERCOT SPP): `DeliveryHour` = **1..24 HOUR-ENDING**, 4×15-min.
  HE `h` covers CDT `[h−1, h)`; its UTC hour-start = `(h−1) CDT + 5h`. Reconstructed hourly RT = mean of
  the 4 intervals; `dart = DA − hourly_mean(RT)`.

## Price provenance (independence, constraint 1)
Realized prices are OURS, never their API. NOTE: the deep `locational/` (RT) + `dam_decade/` (DA) stores
end ~2026-07-01, *before* the forecast window (2026-07-08→08-02), so the window rides our gridstatus-fed
caches — RT from `archive_cache/NP6-905-CD`, DA from `dart_cache/DAY_AHEAD_HOURLY`. Both are our own pulls
of ERCOT settlement, independent of Kardashev.

**Honest observation:** our reconstructed realized RT/DA match their reported `rt`/`da` to the cent — i.e.
their *realized* series is faithful to ERCOT settlement (not cherry-picked). Independence here means we
**recompute** realized from our stores rather than trust their forecast's self-reported outcome; we then
score their *forecast quantiles* (p10/p50/p90) against that independently-computed truth.
