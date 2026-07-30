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

- ADJUSTMENTS from Mike after T5 pause (2026-07-29):
  (A) CUTOFF CORRECTION [committed]: information cutoff now matches the LIVE 16:00 ET / 15:00 CT commit
      EXACTLY (was a more-conservative uniform Dg-2). Features use data <= decision_time; freshest
      same-hour = Dg-1 for delivery H<=14 else Dg-2. dataset.py + leakage_guard.py updated; Houston
      n 74,382->74,373. VERIFIED by checker: per-hour persistence exact both branches, no feature past
      decision_time, trail reconstruction matches, lag48 fixed-Dg-2 distinct from persist, suite 5/5.
  (B) metrics+blend [committed]: $100 spike head added (base rate 1.37%, 891 events, 41/89 folds <5 -> flagged); log-loss added (exposes persistence hard-call miscalibration LL 2.82 vs clim 0.30); per-fold event counts. Blend clim_persist honestly UNDERPERFORMS climatology (pinball 13.54 vs 11.10) â persistence too weak a DART signal. Houston cutoff-corrected persistence 18.67. VERIFIED e-9 (blend formula, $100 Brier/LL/counts, event flags).
      spike probs (no misleading q10-q90 interpolation). Blend baseline 'clim_persist' (clim spread,
      level nudged 0.5x toward persistence). [in progress]
  (C) note framing: model results as Delta vs climatology (%, per quantile, per spike head).
