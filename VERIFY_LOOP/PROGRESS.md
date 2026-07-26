# Progress — Structuring Desk + Desk Table (climatology baseline)

Supervised. Max 8 iterations. ONE task = ONE commit. Honesty contract (GOAL.md) echoed in every commit.
Never commit red. Same check red 3x = blocked.

## Checklist
- [x] 1 — Drop in vol_engine/options_engine/desk_climatology + test_fixtures; fixtures GREEN in conda.
- [x] 2 — /api/vol?hub=&bucket= + desk_data.py. RT from price_store rolling (cached, 48d), DA from
        dart_cache DA-hourly (30d); peak=HE07-22/offpeak=rest (declared in payload). Per market:
        realized_vol 20/60/250 + vol_cone (omits data-thin windows honestly). Excluded-nonpos in payload
        + logged. Real depth only (n_obs==n_days-1). SANITY Houston RT peak $163.4/sqrt-yr (in [10,10000]).
        VERIFIED self (200, multi-hub sane, bad-input no-500, cache) + fresh-eyes GREEN 7/7 (finite, n_obs
        reproduced to the cent, no fabricated 250d cone, magnitude, honest labels, robust, no-LLM/read-only).
        Known cosmetic: vol_engine.py:63 FutureWarning on each call (left as-is). commit <pending>.
- [x] 3 — /api/option governed pricer. F = forward-curve monthly block (cached _forward_curve + sha
        curve_version passed through); vol = realized (task-2 path, caller picks window, echoed in
        vol_source: black76 uses log_vol, bachelier uses normal_vol). policy DECLARED. F<=0 or K<=0 =>
        black76 refusal returned VERBATIM + offer_bachelier (shared ValueError path); bachelier any sign.
        Provenance block (model_policy/vol_source/curve_version/asof/F/K/T) + honest label everywhere.
        Note: offline data_clean curve months are ~stale (front past->T floors 1d); use future month live.
        VERIFIED self + fresh-eyes GREEN 6/6 (F==curve block, window echoed, put-call parity <1e-6 both
        models, verbatim refusal, honest label, robust/read-only). commit <pending>.
- [x] 4 — Structuring panel (Quant card #7 c-struct) + struct() renderer + LOADERS. ATM call/put per
        hub (front FUTURE month, Bachelier, peak) with value + Greeks + per-hub vol_source; shared
        provenance strip (model_policy/curve_version/month/asof + "model value ... not a market quote");
        vega tie-in ("Battery MC vega=+0.038 ... the battery is long exactly what this option prices").
        SCREENSHOT taken + viewed (renders in house style). VERIFIED self + fresh-eyes GREEN 6/6 (populates
        4 hubs, DOM==API to the cent, provenance visible, vega phrase, honesty labels, lazy-load hygiene).
        commit <pending>.
- [ ] 5 — Climatology build → clim_result.json snapshot; honest date-range label.
- [ ] 6 — Desk table tab: per-hour today+tomorrow, Clim P(RT>DA), q05/50/95, n, Your Call, 3 reserved —. Screenshot.
- [ ] 7 — Fresh-clone test + Fly deploy; verify /api/vol, /api/option, desk table on deployed app.

## Append-only log
- init (2026-07-25) — New loop from LOOP_RECIPE.md (dropped in by Mike). Prior loop (daily-rhythm) done
  + pushed (HEAD was 09048b3). Wrote GOAL from the recipe.
- task 1 — Modules dropped in (vol_engine.py, options_engine.py, desk_climatology.py, test_fixtures.py,
  LOOP_RECIPE.md). `conda run -n volt python test_fixtures.py` => ALL PASS (20/20), exit 0: vol recovers
  0.80 & 300 within 5%, negatives counted not hidden, windowed n_obs, cone envelope; B76 parity ~1e-15 +
  Greeks vs finite-diff + F<=0 refusal; Bachelier parity w/ negative F,K + deep-ITM intrinsic; clim
  P(RT>DA)=0.60 planted cell recovered, n counted, desk_rows None on model cols, kind=climatology_baseline.
  Fixtures = SYNTHETIC math only (not the real archive — that's tasks 2/5). Known cosmetic: vol_engine.py:63
  pandas FutureWarning (.fillna downcasting) — not a failure; leave the drop-in as-is, revisit if it reds.
