# GOAL — Probabilistic DART forecast RESEARCH (harness-first, honestly benchmarked)

Research loop. Outputs = metrics, plots, a research NOTE. **NO deploy. NO changes to signal.py or the
live book. NO map/UI work.** Max 14 iterations, ONE task per iteration, ONE commit per task.
PAUSE for Mike's review after Task 5 (harness gate) and at the end. Never commit red; same check red
3× = blocked, stop. Promotion into signal.py is a FUTURE decision of Mike's, not this loop.

## Definition of done
A walk-forward, leakage-guarded evaluation harness (proven able to FAIL cheats) + LightGBM quantile
models with conformal calibration, benchmarked against first-class baselines, per hub, with a
desk-auditable research note in `research/dart_forecast/`.

## HARD CONSTRAINTS (violating any = RED even if metrics look great)
1. **HARNESS BEFORE MODEL.** No model trains until Tasks 1–5 are green. The harness must be proven
   able to FAIL things (sabotage tests) before anything is allowed to pass.
2. **INFORMATION TIMING.** `decision_time` = moment tomorrow's calls are generated (~16:00 ET /
   15:00 CT today, for target day D+1 — matches the live commit leg). EVERY feature carries an
   `available_at`; harness REJECTS any feature with `available_at > decision_time`. FORBIDDEN:
   day-D+1 RT prices, day-D+1 actual weather, anything derived from them. Historical weather ACTUALS
   as forecast stand-ins = lookahead → prefer Open-Meteo Historical FORECAST API (archived forecasts).
   If only actuals exist for a span, that run is labeled in EVERY output it touches:
   **"actuals-as-forecast UPPER BOUND — not achievable live."**
3. **Data hygiene.** No NaN/Inf coercion to values. Bad rows are DROPPED and COUNTED; drop counts
   reported per hub. Deterministic seeds everywhere. Every artifact stamps: git SHA, data span,
   n_samples, seed.
4. **Baselines are first-class.** zero-spread (DA=RT), persistence (same-hour yesterday's DART),
   hourly climatology (reuse existing clim snapshot conventions). If a baseline beats the model, the
   report SAYS SO VERBATIM in the headline. Never the words "profitable", "projected", or "predicts
   spikes" — use "quantile forecast", "P(RT>threshold)", "vs baseline".
5. **Per-hub honesty.** HB_HOUSTON has decade DA+RT; NORTH/SOUTH/WEST are ~1yr RT-limited → their
   results carry a small-sample label and are NEVER averaged into a headline with Houston.
6. **No LLM anywhere in the pipeline.** Tests never touch `journal/` or push. Artifacts → `research/dart_forecast/`.

## Sign convention (state once, use everywhere)
`dart = DA − RT` ($/MWh). Positive dart = DA priced above RT (RT settled cheaper). Spike head of
interest = RT exceeding DA by threshold T → `RT − DA > T` ⇔ `dart < −T`. T stated in code.

## VERIFICATION (maker ≠ checker; fresh-eyes subagent per task)
- Hand re-derivation: checker recomputes pinball loss for one hub/day/quantile and coverage for one
  split from raw arrays, to 6 decimals vs harness output.
- Harness verified by SABOTAGE (Tasks 3 & 5): must catch a planted leak and a shuffled-target model.
  A harness that can't fail a cheat is not a harness.

## TASKS
1. Dataset assembly (per-hub hourly frame; target dart=DA−RT; features w/ available_at; per-hub span+drops).
2. Walk-forward splitter (expanding, monthly retrain, strict temporal order, embargo ≥1 day).
3. Leakage guard + SABOTAGE test (plant dart_tomorrow → guard must reject; test passes by failing the leak).
4. Metrics + report core (pinball q10/25/50/75/90, coverage vs nominal, spike Brier + reliability; JSON+md).
5. Baselines end-to-end through harness (zero-spread, persistence, climatology). ⏸ PAUSE — show baseline table.
6. LightGBM quantile models per hub (Houston first-class; tune ONLY on validation inside train; seeds fixed).
7. Conformal calibration (split-conformal per hub/hour-block; coverage before/after → nominal).
8. SHUFFLED-TARGET GATE (retrain on permuted targets; must NOT beat baselines OOS; else blocked/stop).
9. Calibration + results plots (reliability, PIT/coverage, pinball-vs-baseline, spike reliability; PNGs).
10. Economic overlay (labeled, small-sample): model q-forecasts through COPIED signal rules → hypothetical
    P&L vs baseline inputs; caveat block (virtual fills, no fees; 12-day incumbent +$1,577.23 @ 53.9%).
11. RESEARCH NOTE (research/dart_forecast/NOTE.md) — desk-quant-auditable; findings at evidence strength.

## Env
`conda run -n volt`; `pip install lightgbm` (+matplotlib if missing) inside env. Data: price_store/
dart_cache + DA decade + weather_data + NP6-86-CD per CLAUDE.md.
