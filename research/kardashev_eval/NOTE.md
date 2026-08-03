# Independent scoring of Kardashev Labs' RT-DA spread forecasts — DRAFT

> **DRAFT — NOT FOR PUBLICATION.** Shared with Ashutosh (Kardashev Labs) for factual review first.
> Nothing here is public until both Mike and Ashutosh have cleared it. Every number below is
> reproducible from committed code + a frozen data snapshot; please check them.

## What this is
A third-party scoring of Kardashev's published spread forecasts, run entirely through our own
settlement record. We are **not** re-deriving your models or disputing your realized series — we
independently recompute the realized RT-DA spread from our ERCOT price stores and score your published
quantiles against it, with honest baselines on identical coordinates. The point is an outside,
reproducible read.

## TL;DR (all with n; no significance claimed — the live window is ~25 days)
1. **Both models beat every baseline on average pinball** (climatology, zero-spread, persistence).
2. **Calibration differs by model:** `tft-2026q3` is sharper but under-covers its 80% interval
   (**0.767**); `tft-v2-2026q3` is wider and well-calibrated (**0.840**, near the 0.80 target).
3. **Coverage holds on average but collapses in the spike head:** in the top decile of |spread|, both
   models fall to **~0.60** coverage. But they still crush climatology there (0.60 vs **0.20**), so they
   capture most of the spike — they under-cover it. The leak is on the **downside** (p10) side.

## Method & independence
- **Realized truth is ours.** Realized spread = `RT − DA` (your convention), computed from our own
  ERCOT pulls: DA from `dart_cache/DAY_AHEAD_HOURLY` (gridstatus DAM SPP), RT from
  `dart_cache/REAL_TIME_15_MIN` (hourly mean of the 4×15-min intervals). We never use your `rt`/`da`/
  `spread` fields for scoring. (Aside, in your favor: where we cross-checked, our recomputed realized
  matches your reported `rt`/`da` to the cent — your realized series is faithful to ERCOT settlement.)
- **Frozen snapshot.** We fetched `/forecast/spread/history` (all 15 nodes, `days=90`) + `/latest` once,
  on **2026-08-02**, and froze the raw bytes (`snapshot_2026-08-02/`, per-file sha256 in `manifest.json`).
  All scoring runs on that frozen copy. We attest only to *what your API served on that date* — no stronger.
- **Timing gate.** Only forecasts with `issued_at < ts` (published before delivery) are scored. In the
  frozen set, 0 records violated this.
- **No LLM anywhere in the scoring path.**

## Data scored
- Snapshot: **21,555 records**, 15 nodes, delivery span **2026-07-08 → 2026-08-02** (~25 days), **27
  issuances**, **2 models** (`tft-2026q3`, `tft-v2-2026q3`), quantiles **P10/P50/P90** (your 80% interval).
- **Scoreable (4):** `HB_HOUSTON, HB_NORTH, HB_SOUTH, HB_WEST` — the hubs where we hold verified realized
  prices.
- **Unscored (11), and why:** `HB_BUSAVG, HB_HUBAVG, HB_PAN` + all 8 `LZ_*` — we have no independent
  verified realized-price store for these locations, so scoring them would rest on your numbers, not ours.
- After dedup (your API returns exact-duplicate rows — 2,672 collapsed) and excluding 120 not-yet-settled
  delivery hours, scored **node-hours: tft-2026q3 = 1,576; tft-v2-2026q3 = 1,380**.

## Sign & alignment proof (the gate that blocks everything)
Your target is "RT-DA spread"; ours is `dart = DA − RT`. We proved the mapping empirically before scoring
(`sign_gate.py`): reconstructing 26 delivery hours across 3 days (07-15/20/26, HB_HOUSTON) from our raw
prices matched your published `da` and `spread` with **max error 0.0000** on both. Result:
**`dart = DA − RT = −(your spread)`**; your `[P10, P90]` on spread ⇒ dart in `[−P90, −P10]`. Timezone:
your `ts` is a UTC hour-start; CDT = UTC−5 for the whole (summer) window. We score directly in your spread
convention, so the tables below read against your published p10/p50/p90 with no sign juggling.

## Results — per model, baselines on each model's OWN identical coordinates
Pinball per quantile (lower better); coverage of the 80% interval (target 0.80). n = node-hours.

| forecast | n | pin@0.1 | pin@0.5 | pin@0.9 | **pin_avg** | **coverage** |
|---|---|---|---|---|---|---|
| **tft-2026q3** | 1576 | 1.006 | 2.767 | 1.595 | **1.789** | **0.767** |
| — climatology | 1576 | 1.621 | 3.063 | 1.893 | 2.192 | 0.834 |
| — zero-spread | 1576 | 4.470 | 3.264 | 2.057 | 3.264 | — (point) |
| — persistence | 1576 | 3.710 | 3.616 | 3.522 | 3.616 | — (point) |
| **tft-v2-2026q3** | 1380 | 1.119 | 3.127 | 2.427 | **2.224** | **0.840** |
| — climatology | 1380 | 1.726 | 3.192 | 1.979 | 2.299 | 0.822 |
| — zero-spread | 1380 | 4.828 | 3.451 | 2.075 | 3.451 | — (point) |
| — persistence | 1380 | 3.830 | 3.614 | 3.398 | 3.614 | — (point) |

Baselines, on identical dates/hours/locations: **climatology** = deep-history spread quantiles by
(hub, hour-of-day); **zero-spread** = predict 0; **persistence** = prior-day realized (point). Per-hub
coverage (tft / tft-v2): HOU 0.751 / 0.809, NORTH 0.772 / 0.864, SOUTH 0.749 / 0.846, WEST 0.797 / 0.841.

**Independent re-derivation (maker≠checker):** a second party recomputed HB_HOUSTON / 2026-07-20 /
tft-v2 from raw prices without our scoring code → pinball **0.976 / 2.691 / 0.794**, coverage **3/3** —
exact match.

## Tail focus — top-decile |spread| (your admitted pain)
Tail = |realized spread| ≥ **$13.09** (top decile of 1,676 unique delivery-hours; **168 tail hours**).

| forecast | bucket | n | coverage | pin_avg | PIT_p10 (t .10) | PIT_p90 (t .90) |
|---|---|---|---|---|---|---|
| tft-2026q3 | calm | 1411 | 0.787 | 1.244 | 0.137 | 0.923 |
| tft-2026q3 | **tail** | 165 | **0.600** | 6.449 | 0.255 | 0.855 |
| tft-v2-2026q3 | calm | 1221 | 0.869 | 1.436 | 0.084 | 0.952 |
| tft-v2-2026q3 | **tail** | 159 | **0.616** | 8.278 | 0.283 | 0.899 |
| climatology | **tail** | ~162 | **~0.21** | ~9.2 | ~0.59 | ~0.80 |

- **Coverage collapses calm→tail** for both models (~0.79–0.87 → ~0.60): the clip-then-widen 80% interval
  under-covers the spike head.
- **But both beat climatology decisively in the tail** (~0.60 vs 0.21 coverage; pinball 6.4–8.3 vs ~9.2).
- **The leak is asymmetric/downside:** in the tail, `PIT_p10` rises to 0.26–0.28 (nominal 0.10) — ~1-in-4
  tail spreads fall below the p10 floor; you under-predict the magnitude of the big down-moves. The upper
  edge (p90) is closer to right.
- **tft-v2's extra width is spent on the calm bucket, not the tail** (tail coverage 0.616 ≈ v1's 0.600).

## Limitations (please weigh these)
- **Small window.** ~25 days, 27 issuances; tail buckets are ~160 hours. Everything is reported as an
  observation with its n — **no significance claims**.
- **11 of 15 locations unscored** for lack of independent ground truth on our side (listed above).
- **API-as-served.** We attest only to what your API served on 2026-08-02 (frozen), not to any claim about
  your production behavior before or after.
- **Store-seam (verbatim):** *window realized prices cent-validated against ERCOT; the climatology
  baseline's deep DA prior rests on convention-continuity across the store seam (June DAM has aged out of
  MIS and cannot be re-fetched).* The scored realized truth is cent-validated; only the climatology
  baseline's deep prior rests on convention-continuity (RT side cent-matched; DA side has no overlapping
  day to cent-match).
- **Going forward,** we now capture your `/latest` daily into a committed, timestamped witness record, so
  future scoring is attestable by us rather than resting on API history.

## How to check every number
All in `research/kardashev_eval/`: frozen data `snapshot_2026-08-02/` (+ `manifest.json` sha256s);
`sign_gate.py` (sign proof), `score.py` (pinball/coverage/baselines), `tail.py` (regime split);
supporting notes `SCHEMA.md`, `MAPPING.md`, `CONTINUITY.md`, `TAIL.md`. Each script prints its full
table and its n's; re-running reproduces the numbers above.

## What we're asking
A factual review: are the sign mapping, the scoreable-location choice, the timing gate, and the baseline
definitions fair to your models? Flag anything mischaracterized. Nothing is published until you and Mike
both clear it.
