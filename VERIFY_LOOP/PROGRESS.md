# Progress — Probabilistic DART forecast research (harness-first)

Supervised. Max 14 iterations. ONE task = ONE commit. Never commit red. Same check red 3× = blocked.
Maker ≠ checker: a fresh-eyes subagent verifies each task. ⏸ PAUSE after Task 5 and at the end.
Artifacts → research/dart_forecast/. Tests never touch journal/ or push. No LLM in the pipeline.

## Checklist
- [ ] 0 — Setup: GOAL.md + PROGRESS.md + data-landscape scout (schemas, timing, spans per hub).
- [ ] 1 — Dataset assembly (per-hub hourly frame, target dart=DA−RT, features+available_at, spans+drops).
- [ ] 2 — Walk-forward splitter (expanding, monthly, embargo ≥1d, strict chronology).
- [ ] 3 — Leakage guard + SABOTAGE test (plant dart_tomorrow → rejected).
- [ ] 4 — Metrics + report core (pinball, coverage, spike Brier/reliability; JSON+md writers).
- [ ] 5 — Baselines end-to-end (zero-spread, persistence, climatology) → baselines_result.json + plots. ⏸ PAUSE.
- [ ] 6 — LightGBM quantile models per hub.
- [ ] 7 — Conformal calibration (coverage before/after).
- [ ] 8 — SHUFFLED-TARGET GATE (must not beat baselines OOS).
- [ ] 9 — Calibration + results plots (PNGs).
- [ ] 10 — Economic overlay (labeled, copied signal rules).
- [ ] 11 — RESEARCH NOTE.

## Append-only log
- init (2026-07-29) — New research loop from Mike's spec. Overwrote the prior Bolt-loop GOAL/PROGRESS.
  Standing constraints carried in: never write journal/, no deploy, no signal.py edits, no map/UI.
  Next: scout the data landscape (price_store, dart_cache, DA decade, weather_data, NP6-86-CD, clim
  snapshot conventions, signal rules to COPY for Task 10) before Task 1.

- T4 note (2026-07-29) — LEAK CAUGHT during T4 design: the static clim_result.json snapshot is built
  on the FULL decade (incl. test periods), so its quantiles are lookahead if used as model FEATURES or
  as a BASELINE. Fix: climatology must be recomputed PER-FOLD from TRAIN data only (reuse the
  month-hour binning convention + min-samples rule, NOT the snapshot values). Action: T5 builds
  train-only fold_climatology(); the static clim_* columns are EXCLUDED from model inputs (kept in the
  frame for reference only). Metrics spike event = dart < -T (RT - DA > T, "RT spike above DA"),
  T stated in code (SPIKE_T). Quantiles per spec: 0.10/0.25/0.50/0.75/0.90.
