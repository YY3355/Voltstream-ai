# Kardashev snapshot — schema & what we actually have (Task 1)

**Frozen:** `snapshot_2026-08-02/` (raw bytes + `manifest.json` with per-file sha256 + fetch UTC).
**Source:** `https://data.kardashevlabs.org` (public, no auth) — `GET /forecast/spread/history?node_id=<id>&days=<n≤90>`
(per-node history) + `GET /forecast/spread/latest` (current issuance, all nodes). Fetched once, politely
(sequential, 1.5s spacing, identifying UA). **Attestation (constraint 3):** these are the forecasts *as
served by their API on 2026-08-02*; we do not verify their values — we score them against OUR settlement
record. All scoring runs on this frozen copy, never a live re-fetch.

## Record schema (per JSON object)
| field | meaning | used in scoring? |
|---|---|---|
| `ts` | delivery hour, **UTC**, `+00:00` (e.g. `2026-07-26T23:00:00+00:00`) | yes (join key) |
| `issued_at` | published-at, **UTC**, µs precision (the vintage / timing gate) | yes (timing filter) |
| `node_id` | location (15; see below) | yes (join key) |
| `p10`,`p50`,`p90` | spread **quantiles** (their 80% central interval = P10–P90) | **yes — the object scored** |
| `da` | their day-ahead price | **NO** — constraint 1, we use OUR DA |
| `model` | `tft-2026q3` or `tft-v2-2026q3` (two models per node) | scored separately per model |
| `rt` (history only) | their realized RT price | **NO** — constraint 1, we use OUR RT |
| `spread` (history only) | their realized spread; **= `rt − da`** (e.g. da 35.46, rt 33.46 → −2.0) | NO (independence); but see sign gate |
| `covered`,`side`,`pnl`,`cooldown` (history only) | their coverage flag + trading-strategy fields | NO |

## Sign convention (PRELIMINARY — proven empirically in Task 2)
Their realized `spread = rt − da` (RT−DA), read directly from the data. Ours is `dart = DA − RT`. So the
expected mapping is **`their_spread = −dart`** — a P10/P90 interval on their spread maps to a −P90/−P10
interval on dart. **Task 2 must PROVE this by reconstructing 3 known days from raw prices both ways and
matching their published values before ANY scoring** (constraint 2 blocks downstream on this).

## What we have
- **21,555 records** across **15 nodes**, delivery span **2026-07-08 07:00 → 2026-08-02 19:00 UTC** (~25 days).
- **27 distinct issuances** (`issued_at`); **0 records with `issued_at ≥ ts`** (all timing-valid).
- **2 models** (`tft-2026q3`, `tft-v2-2026q3`); e.g. HB_HOUSTON = 743 + 694 records, 434 distinct delivery hours.
- **Quantiles:** P10, P50, P90 only (no other quantiles published).
- **Locations (15):** 7 hubs `HB_BUSAVG HB_HOUSTON HB_HUBAVG HB_NORTH HB_PAN HB_SOUTH HB_WEST` +
  8 load zones `LZ_AEN LZ_CPS LZ_HOUSTON LZ_LCRA LZ_NORTH LZ_RAYBN LZ_SOUTH LZ_WEST`.

## Scoreable vs unscored (constraint 5)
- **SCOREABLE (4):** `HB_HOUSTON HB_NORTH HB_SOUTH HB_WEST` — overlap our verified `locational/` RT-SPP
  coverage (all 4 hubs) + DA in `dam_decade/`.
- **UNSCORED (11), and why:** `HB_BUSAVG HB_HUBAVG HB_PAN` + all 8 `LZ_*` — no verified realized-price
  store on our side for these locations, so scoring them would rest on their numbers, not ours. Listed
  in the note as unscored-for-lack-of-independent-ground-truth.

## Timezone / hour convention
All timestamps UTC. Delivery `ts` lands on the hour (`:00`). Whether `ts` is hour-ENDING or hour-BEGINNING
vs our stores' convention is **pinned in Task 2** alongside the sign proof (a 1-hour misalignment would
corrupt every join).
