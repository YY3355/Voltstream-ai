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
- [x] 5 — build_clim.py → clim_result.json snapshot (committed, decade/hedge pattern, repo root NOT
        journal/). Per-hub DART climatology from real archive DA/RT hourly PAIRS (~720h/hub, span
        2026-06-25..07-24). HONEST: pairs only cover the rolling window, labeled "NOT a decade";
        MIN_SAMPLES=30 hard rule -> 0/192 cells sufficient (all "—"), the correct thin-data outcome, not
        fabricated. Logs hours+range. VERIFIED self + fresh-eyes GREEN 6/6 (honest range, no fabricated
        cells, n reproduced independently=720, DART math <1e-9, root/not-journal, no-LLM). commit <pending>.
- [x] 6 — /api/desk + Desk Table panel (Trading card #4 c-desk) + desk() renderer + LOADERS. Per-hour
        today+tomorrow: DA (real from cache, "—" until DAM — honest, offline cache stale so all "—"),
        Clim P(RT>DA)+DART q05/50/95+n from clim snapshot ("—" where n<30 = all here), Your Call from
        dart_journal (READ-ONLY, matches exactly), 3 reserved model_p/load/wind cols "—" with ⓘ tooltip
        "roadmap, not built". No "Model" prob label (Clim P(RT>DA) header). SCREENSHOT taken + viewed.
        VERIFIED self + fresh-eyes GREEN 6/6 (contract, NO journal write [md5 identical], your_call==journal,
        renders, tooltip/no-Model, honest —/lazy-load). commit <pending>.
- [x] 7 — Fresh-clone test (deep snapshots stand alone, no caches: /api/vol snapshot + /api/desk clim +
        /api/option all served from a clean checkout) + Fly REDEPLOY to existing machine (7845467b249768,
        v17->19, NO new machines/volumes/regions/scale). First deploy hit a snapshot-bug: .dockerignore
        `*.json` excluded clim/vol_result.json (not in the ! exceptions) — the raw-clone test missed it
        (didn't build the image). FIXED: added !clim_result.json + !vol_result.json + absolute paths in
        app.py; redeployed. LIVE voltstream-ercot.fly.dev VERIFIED: /api/vol source='committed deep
        snapshot' 250d cone, /api/desk 2018-2026 climatology 24/24 real ClimP, /api/option prices, desk
        table renders with real Clim P(RT>DA)%. commit <pending>. LOOP COMPLETE.

## Deep-archive upgrade (pre-task-7, Mike-requested) — evidence + rebuild
- (a) deployed serves climatology from COMMITTED clim_result.json (app.py reads it; build_climatology
  never called in server; tracked + not dockerignored). (b) Fly /data ~23 DA+23 RT days from 2026-07-03
  (~3wk) via read-only fly ssh — shallower than local.
- Found NP4-190-CD "DAM Settlement Point Prices" with 102 monthly bundles 2018-01..2026-06 (DA decade,
  analog of the RT SPP decade). RT decade already cached (data_archive/decade/, HB_HOUSTON 2018+).
- Backfilled the DA decade (scripts/backfill_dam.py -> data_archive/dam_decade/, gitignored). DAM parser
  validated to the CENT vs independent dart_cache DA. scripts/build_snapshots.py merges RT (decade+data/+
  store) ∩ DA (dam_decade+dart_cache) -> clim_result.json + vol_result.json.
- REBUILT NUMBERS: pair span 2018-01-02..2026-07-24. cells_sufficient 455/1152 (HB_HOUSTON 288/288 all,
  n~272/cell; NORTH 70, SOUTH 49, WEST 48 — RT-limited to data/ 1yr, honest per-hub). vol cone 250d
  n_obs=250, 2877 samples (HB_HOUSTON both markets). /api/vol now PREFERS vol_result.json (deep) over the
  thin live store; /api/desk serves the deep clim (HB_HOUSTON 24/24 real Clim P(RT>DA)). Screenshot taken.
- Gate MET (sufficient cells>0 AND cone real depth) -> proceed to fresh-clone + hold fly command for Mike.

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
