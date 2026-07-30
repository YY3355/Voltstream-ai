# DART forecast research — data provenance & scope (verified 2026-07-29)

All facts below were verified by reading the raw stores in the `volt` env, not inferred.

## Sign convention (CANONICAL for this research)
`dart = DA − RT` ($/MWh). Positive = DA settled rich (RT cheaper). Matches `dart_engine.py:56`
(`dart = da - rt`), the live book, and the signal rules in `dart_journal.py` (which we COPY, never
edit, for the Task-10 economic overlay).

### ⚠ Sign-convention TRAP (load-bearing)
`desk_climatology.py:27` uses the OPPOSITE sign: `dart = rt - da`. So everything in
`clim_result.json` — `p_rt_gt_da`, `dart_mean`, `dart_q` — is in **RT − DA** units. To use the
climatology as a baseline forecast of our canonical target (DA − RT), we must apply a tested
adapter: `target_q[q] = −(clim_q[1−q])` (e.g. our q10 = −(clim's q90), our q50 = −(clim's q50)).
This adapter is unit-tested and the hand-re-derivation checker (Task 5) confirms it on real cells.

## Spike head of interest
`RT − DA > T` (RT exceeds DA by threshold) ⇔ `dart < −T`. T stated in code (Task 4). Reported strictly
as a probability `P(RT − DA > T)` — a quantile/probability forecast, not a spike-prediction claim.

## Data stores (verified paths / shapes / spans)
| What | Path | Shape / key | Span | Hubs |
|---|---|---|---|---|
| DA hourly (decade) | `data_archive/dam_decade/{2018..2026}.pkl` | DataFrame, DatetimeIndex (naive), cols=4 hubs | 2018-01-02 → 2026-07-01 (74,463 h) | **all 4** |
| RT 15-min (decade, Houston) | `data_archive/decade/{2017..2026}.pkl` | Series `HB_HOUSTON_rt_spp` (naive) | 2018-01-01 → 2026-06-30 (297,846×15min) | Houston |
| RT 15-min (decade, ALL hubs) | `data_archive/locational/{hub}.pkl` | Series `{hub}_rt_spp` (naive), 15-min | 2017-12-31 → 2026-06-30 (297,846 each) | **all 4** (repoint source, Task 0) |
| DA hourly (recent) | `dart_cache/DAY_AHEAD_HOURLY_*.pkl` | df, `Location`/`SPP`, tz=US/Central | 2026-06-29 → 2026-07-28 (30 d) | all hubs |
| RT 15-min (recent) | `dart_cache/REAL_TIME_15_MIN_*.pkl` | df, tz=US/Central | 2026-06-29 → 2026-07-28 (30 d) | all hubs |
| RT archive (settled) | `data_archive/archive_cache/NP6-905-CD_*.pkl` | df, 96 rows/day = 1 hub | 2026-06-07 → 2026-07-28 (52 d) | Houston (sampled) |
| Constraints (SCED) | `data_archive/archive_cache/NP6-86-CD_*.pkl` | df, ShadowPrice/ConstraintName/from,toStation | 2026-06-23 → 2026-07-29 (37 d) | grid-wide |
| Climatology snapshot | `clim_result.json` | `{hub:{cells:{"M-H":{p_rt_gt_da,dart_mean,dart_q}}}}` (RT−DA sign!) | Houston decade; others ~1yr | all 4 |

### Verified per-hub PAIRED (DA∩RT) span
- **HB_HOUSTON**: **74,439 h, 2018-01-02 → 2026-06-30, all 9 years** — first-class.
- **HB_NORTH / HB_SOUTH / HB_WEST**: **UPDATE (Task 0 repoint):** RT is now a decade for these hubs via
  `data_archive/locational/{hub}.pkl` (was ~28-day `dart_cache`). Paired frame = 74,373 h each,
  2018-01-04 → 2026-06-30 — same as Houston. Baselines re-run as the full decade walk-forward. They are
  no longer small-sample; per-hub numbers are still reported separately, never averaged with Houston.
  (Original note preserved for history:) DA is decade; the older RT decade store `data_archive/decade/`
  was Houston-only, so before the repoint N/S/W were ~28-day. If raw RT
  proves too thin for modeling, they get baselines + climatology only — stated plainly.

## Timezone
dart_cache is tz-aware US/Central; decade stores are tz-naive (wall-clock Central). We standardize to
**tz-naive Central** via `.tz_localize(None)` (matching `dart_engine._hourly_by_hub`). DST gaps/dupes
are dropped-and-counted, never coerced.

## decision_time & feature availability
`decision_time` = 16:00 ET (15:00 CT) on day D, for target delivery day D+1 (matches the live commit
leg, `dart_journal.cmd_commit`). At that instant the DAM for D+1 has cleared, so:
- **ALLOWED**: DA curve for D+1 (hourly, per hub); any RT/DART stat with timestamp ≤ end of day D;
  hourly climatology; calendar. Each feature carries an `available_at`.
- **FORBIDDEN** (lookahead): D+1 RT prices, D+1 actual weather, anything derived from them.
- Weather/wind: `weather_data.py` serves only the CURRENT forecast (no archived forecasts). For a
  lookahead-clean backtest we use Open-Meteo's Historical **Forecast** API (archived forecasts, 2022+).
  Any span forced to fall back to weather ACTUALS is labeled "actuals-as-forecast UPPER BOUND — not
  achievable live" in every output it touches.

## Feature registry scope (realized vs registered-deferred)
Task 1 realizes the **price + calendar + climatology** backbone (fully available, decade-spanning).
The **weather/wind (net-load proxy)** and **constraint-binding** groups are registered in the feature
schema with their `available_at` rule and coverage (weather 2022+ archived-forecast; constraints
2026-06+), and added at the model stage (Task 6) — never hidden, always coverage-labeled. Nothing
lookahead enters the backbone.

## Env
`volt` conda env. Installed: pandas≥2, numpy≥1.26, scikit-learn≥1.4. NOT installed: **lightgbm**,
**matplotlib** — `pip install` inside the env at the tasks that need them (6 and 5/9), never before
(harness-before-model).
