# Probabilistic DART forecasting for ERCOT — research note

**Scope.** Can a machine-learned quantile model forecast next-day hourly **DART = DA − RT** ($/MWh) at
ERCOT trading hubs better than first-class baselines, *at the exact information set of the live 16:00 ET
commit*, and is any edge real? This is research: the deliverables are metrics, calibration, and this
note. **Nothing here is promoted into `signal.py` or the live book — that is a separate, future
decision.** Findings are stated at evidence strength (e.g. "beats climatology pinball by 46.7% on
Houston q90"), never "it works".

All results are reproducible from committed artifacts; every claim links to a JSON/figure/module and was
checked by an independent fresh-eyes agent (maker ≠ checker) — see the per-task commits.

---

## 1. Data & provenance (verified, not inferred)

Sign convention (canonical): **`dart = DA − RT`**, positive = DA settled rich (RT cheaper). Matches
`dart_engine.py:56` and the live signal rules.

> ⚠ **Sign trap.** `desk_climatology.py:27` and `clim_result.json` use the OPPOSITE sign (RT − DA). The
> climatology adapter flips it: our `q_τ = −(clim_q_{1−τ})`, `P(DA>RT)=1−clim.p_rt_gt_da`. Tested; the
> checker confirmed `clim_q10 = −(clim q90 of RT−DA)` on real cells.

| Hub | Paired DA∩RT span | n (model frame) | Drops (dropped **and** counted) | Status |
|---|---|---|---|---|
| **HB_HOUSTON** | 2018-01-04 → 2026-06-30 (decade) | **74,373** | 34 incomplete/nonfinite pairs + 66 warm-up | first-class |
| HB_NORTH / SOUTH / WEST | 2026-07 only (~28 days) | 672 each | 0 bad pairs + 48 warm-up | ⚠ small-sample |

DA is a decade for all four hubs (`data_archive/dam_decade/`); the **RT decade store is Houston-only**
(`data_archive/decade/`), so NORTH/SOUTH/WEST are RT-limited to ~28 days from committed caches. They
carry a small-sample label and are **never averaged into a headline with Houston.** Data hygiene: no
NaN/Inf coercion — bad rows dropped+counted; trailing features that are simply not-yet-warmed are kept
as model-native missing, never imputed. Full provenance in `DATA_SOURCES.md`; per-hub drop counts in
`dataset_meta.json`.

## 2. Information timing (the load-bearing constraint)

`decision_time = 16:00 ET / 15:00 CT on day D` for delivery day D+1 — the live commit leg. Features use
**only** data with timestamp ≤ decision_time. The freshest same-hour lag is day D for delivery hours
H≤14 (the 14:00 CT hour is complete by 15:00) and day D−1 for H≥15. The DA curve for D+1 is admissible
(DAM clears ~13:30 CT). This *matches the live decision exactly* (a corrective change after an initial
over-conservative D−2 cutoff — see commit `fa6c18d`).

Two leakage gates:
- **Declared-provenance gate** (`leakage_guard.py`): every feature must be registered with an
  `available_at` ≤ decision_time (fails closed on unknown columns). Sabotage suite `tests/test_leakage.py`
  (5/5): a planted `dart_tomorrow` and a delivery-time feature are both rejected.
- **Statistical backstop** (§7): the declared gate trusts labels; the shuffled-target gate catches leaks
  regardless of declaration.

## 3. Methods (all pure, hand-checkable, seed=42)

`dataset.py` (frame + available_at registry) → `splitter.py` (expanding, **monthly retrain**, embargo
≥1 day, strict chronology; 89 Houston folds 2019-02→2026-06) → `metrics.py` (pinball q10/25/50/75/90;
coverage; spike Brier + **log-loss** + reliability at T∈{$20,$100}; per-fold event counts) →
`baselines.py`, `model.py`, `conformal.py`, `shuffle_gate.py`, `overlay.py`. LightGBM 4.7 (quantile
objective per τ; binary spike classifiers), `num_threads=1, deterministic=True, force_row_wise=True` →
bitwise reproducible. Climatology is recomputed **per-fold on train only** (the committed full-decade
`clim_result.json` snapshot is lookahead and is *excluded* from model features).

## 4. Baselines (walk-forward, pooled OOS) — `baselines_result.json`

**HB_HOUSTON, 89 folds, n=64,944 (2019-02→2026-06):**

| baseline | mean pinball | 10–90 cov | spike LL $20 | spike LL $100 |
|---|---|---|---|---|
| **climatology** (train-only) | **11.10** | 0.694 | 0.295 | 0.171 |
| zero-spread (dart=0) | 12.19 | 0.000 | 1.611 | 0.474 |
| persistence (fresh same-hour) | 18.67 | 0.000 | 2.818 | 0.836 |
| clim_persist (blend, w=0.5) | 13.54 | 0.660 | 0.295 | 0.171 |

**Climatology is the bar to beat.** Persistence is a *weak* DART baseline (18.67 ≫ 12.19) — yesterday's
DART poorly predicts tomorrow's. The persistence→climatology blend **underperforms** pure climatology
(13.54 vs 11.10): nudging the climatological level toward a noisy signal adds variance (honest negative).
Spike base rates: $20 → 4.67% (3,030 events, 2/89 sparse folds); **$100 → 1.37% (891 events, 41/89 folds
have <5 events — flagged hollow; log-loss, not Brier, is the informative tail metric).**

## 5. Model results — Δ vs climatology (`model_result.json`)

LightGBM quantile models, **HB_HOUSTON, 78 eval folds, n=56,931 (2020-01→2026-06)**; hyperparameters
tuned on an inner validation carved from a **pre-2020 block that is provably disjoint from every eval
test row** (checker: intersection = 0). Reported as Δ% vs climatology recomputed on the *same* folds.

| metric | model | climatology | **Δ vs climatology** |
|---|---|---|---|
| mean pinball | 9.23 | 10.83 | **−14.8%** |
| pinball q10 | — | — | −9.9% |
| pinball q25 | — | — | **+7.7% (worse)** |
| pinball q50 | — | — | −4.1% |
| pinball q75 | — | — | −27.2% |
| pinball q90 | — | — | **−46.7%** |
| spike log-loss $20 | 0.200 | 0.294 | −32.0% |
| spike log-loss $100 | 0.085 | 0.169 | −49.7% |

**Evidence-strength statement:** on HB_HOUSTON (2020–2026, walk-forward, decision-time-clean), the
LightGBM quantile model **beats the train-only climatology by 14.8% in mean pinball, with the gains
concentrated in the upper tail (q75 −27.2%, q90 −46.7%) and in spike-head log-loss (−32% at $20, −50% at
$100).** It is **slightly worse at q25 (+7.7%)**, and its raw interval coverage (~0.69) is essentially
unchanged from climatology — the model sharpens the tail but does not self-calibrate. See
`fig_pinball_vs_baseline.png`, `fig_coverage_pit.png`, `fig_spike_reliability.png` (the model's spike
curves are more *resolved* than climatology's flat cell-rates but somewhat *overconfident* at high
predicted probability).

## 6. Calibration — split-conformal / CQR (`conformal_result.json`, `fig_conformal_blocks.png`)

Per hour-block (6× 4h), calibration = last 90 days of each fold's train (disjoint from fit, pre-test):

| interval | coverage before → after | width before → after |
|---|---|---|
| 80% (q10/q90) | 0.694 → **0.798** (nominal 0.80) | 57.7 → 61.7 |
| 50% (q25/q75) | 0.405 → **0.505** (nominal 0.50) | 21.3 → 23.2 |

Calibration reaches nominal by **widening**, not narrowing (width is reported so a narrower-miscalibrated
band can't masquerade). Per-block conditioning captures the peak-hour volatility (evening 16–19 band
~$122/MWh vs night ~$24).

## 7. Shuffled-target gate — the anti-leak backstop (`shuffle_gate_result.json`)

Retrain the exact pipeline on **permuted training targets**; a clean pipeline can only recover the
unconditional marginal → must not beat climatology.

- shuffled-target model mean pinball **11.03 (+1.9% vs climatology)** — does **not** beat it.
- real model **9.23 (−14.8%)** → **the edge collapses under label permutation.**

**The −14.8% edge is genuine learned signal, not leakage or a pipeline artifact.** GATE PASSED (the
assertion is non-vacuous — the checker confirmed it blocks a beats-climatology input, and a real-label
fit with a planted leak column collapses pinball to 0.51, which would trip it).

## 8. Economic overlay — LABELED, HYPOTHETICAL (`overlay_result.json`)

Model q50 fed through a **copy** of the live signal rule (`position = sign(bias)` if `|bias|>$1`;
`pnl = position × realized_dart`, 1 MW·h; live file untouched) vs the same rule on baseline inputs,
Houston 2020–2026, n=56,931 hours:

| rule input | hypothetical P&L | hit rate |
|---|---|---|
| climatology q50 | **+$142.0k** | 68.2% |
| model q50 | +$77.9k | 66.8% |
| trailing bias (incumbent-style) | −$34.1k | 56.9% |

**Honest negative:** the model's forecast superiority does **not** translate into better P&L under this
naive **sign** rule — climatology's near-always-long stance (long 0.69 / short 0.00) harvests the
structural DART premium (DA usually rich) better than the model's more nuanced median. **The model's
economic value lives in its quantiles/tail (risk sizing, spike probabilities), not the sign of the
median.** P&L is tail-dominated (2023-08-15 alone = $11.8k, a real scarcity afternoon: max DART
$2,973/MWh, 8 hours |dart|>100).

> **CAVEATS.** Hypothetical; virtual fills at settlement; no execution/fees/slippage/risk-limits; 1 MW
> clips; single hub. **No statistical-significance claims.** The live paper book (+$1,577.23 over 12 days
> @ 53.9%) is **context only** — different period, scale, and construction; do **not** compare directly.

## 9. Limitations (read before trusting any number)

1. **Hub-sample asymmetry.** Only HB_HOUSTON has a decade of paired DA/RT. NORTH/SOUTH/WEST are ~28-day,
   baselines/climatology only, never merged with Houston. Multi-hub modeling needs an RT backfill
   (explicitly out of this loop's scope).
2. **Weather / net-load features are NOT in the model.** They are registered-deferred. Doing them
   right needs Open-Meteo's Historical **Forecast** API (archived forecasts, 2022+); using weather
   *actuals* as forecast stand-ins is lookahead and any such run must be labeled
   *"actuals-as-forecast UPPER BOUND — not achievable live."* The current model is price + lag +
   calendar + per-fold-climatology only. Adding forecast-sourced wind/load is the most promising
   unexplored lever.
3. **Regime breaks.** The 2018–2026 span crosses Winter Storm Uri (Feb 2021), the 2022 volatility
   regime, and **RTC+B** (Real-Time Co-optimization + Batteries, ERCOT's Dec-2025 market redesign). The
   walk-forward retrains monthly but does **not** model these breaks explicitly; pinball is pooled across
   regimes. Post-RTC+B (2026) behavior is only ~6 months of test and may not resemble history.
4. **The $100 spike head is sparse** (41/78 eval folds <5 events). Trust the pooled **log-loss**, not
   per-fold Brier; treat $100 numbers as directional.
5. **Coverage vs sharpness.** Raw model intervals undercover (~0.69); use the conformal layer (§6) for
   any interval claim.
6. **The overlay's sign rule ignores the model's actual edge** (the tail/quantiles) — see §8.
7. **Environment.** LightGBM on macOS needs a libomp symlink
   (`ln -sf $CONDA/lib/libomp.dylib $CONDA/envs/volt/lib/libomp.dylib`); results are single-threaded for
   determinism.

## 10. Next questions

- A decision rule that **uses the quantiles and spike probabilities** (position sizing, tail-risk limits,
  P(RT−DA>$T)-gated entries) instead of the sign of the median — this is where §5/§8 suggest the value is.
- Forecast-sourced **wind / net-load** features (Open-Meteo archived forecasts, 2022+), properly
  `available_at`-stamped.
- **RTC+B regime-aware** evaluation: a separate post-2025 model/holdout, and a regime feature.
- Multi-hub once NORTH/SOUTH/WEST RT is backfilled (congestion/basis structure).
- Spike-specialised models and conformalized spike probabilities for the $100 tail.

## 11. Reproducibility

Env: conda `volt` + `pip install lightgbm matplotlib` + the libomp symlink above. Seed 42 everywhere;
every artifact stamps git SHA / span / n / seed. Run order:
`dataset.py` → `splitter.py` → `tests/test_leakage.py` → `metrics.py` → `baselines.py` → `model.py` →
`conformal.py` → `shuffle_gate.py` → `plots.py` → `overlay.py`. Each task is one commit with an attached
independent-checker verdict; the harness was proven able to **fail cheats** (sabotage leak + broken
splits + shuffled targets all rejected) before any model was trusted.
