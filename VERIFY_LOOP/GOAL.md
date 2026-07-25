# GOAL — Structuring Desk + Desk Table (climatology baseline)

Full spec: LOOP_RECIPE.md (checked in). Supervised, Opus, max 8 iterations, ONE task = ONE commit.
Env: `conda run -n volt`; `ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean` for CSV mode; kill stale :8020;
warm /api/dart + /api/risk before render checks; headless-Chrome/CDP render per tab; screenshots for
every visual task.

## Honesty contract (NON-NEGOTIABLE — echo in commit messages)
- Realized vol labeled "realized, not implied — no option quotes available" everywhere it renders.
- Option values labeled "model value under realized vol — not a market quote."
- Desk table probability column = "Clim P(RT>DA)". The word "Model" appears NOWHERE until an
  eval-harnessed model ships. model_p / load_fcst / wind_fcst render as "—".
- Cells with n < 30 samples render "—", never a number.
- No vol surface. No implied anything. No smoothing across (month,hour) cells.

## Tasks (in order — see LOOP_RECIPE.md for full detail)
1. Drop in vol_engine.py, options_engine.py, desk_climatology.py; run test_fixtures.py in conda. Green
   = commit. (Fixtures prove math on SYNTHETIC data only — say so in the commit message.)
2. /api/vol?hub=&bucket= off price_store DA/RT (peak=HE7–22 avg, offpeak=rest; declare def in payload).
   realized_vol for 20/60/250d + vol_cone. Verify finite, n_obs==archive len, excluded-day counts
   logged. SANITY: Houston normal vol same order as historical DART swings; <$10 or >$10,000/sqrt-yr => STOP.
3. /api/option — hub, month, strike, type, model policy. F from bootstrapped forward curve (pass version).
   vol from task 2 (window echoed in vol_source). Any monthly forward ≤ 0 => black76 returns its refusal
   verbatim; UI offers bachelier.
4. Structuring panel (Quant tab): ATM call/put card per hub front month — value + Greeks + provenance
   block (model_policy, vol_source, curve version, asof) VISIBLE + vega tie-in to Monte-Carlo battery
   result. Screenshot required.
5. Climatology build: build_climatology per hub from full archive → clim_result.json (committed
   snapshot, decade/hedge pattern, Fly volume caveat). Log total hours + date range; LABEL the true
   range honestly (no implied decade coverage the data lacks).
6. Desk table tab/panel: per-hour today+tomorrow — DA (real, "—" until DAM), Clim P(RT>DA), clim DART
   q05/q50/q95, n, Your Call (dart_journal if present), 3 reserved "—" cols w/ ⓘ tooltip (roadmap,
   not built). Mirror per-MTU desk layout. Screenshot required.
7. Fresh-clone test + Fly deploy; verify /api/vol, /api/option, desk table render on deployed app.

## Verify discipline
Fresh-eyes subagent per task (maker≠checker). Curl endpoints → 200 + sane numbers (assert independently).
Render each touched tab headless; screenshots for visual tasks. Never commit red. Same check red 3x = blocked.

## OUT OF SCOPE (do not drift)
Option taxonomy lists, barrier/Asian/swing, implied vol, spark spreads (no gas curve), any forecast
model, any "Model P(up)" number.
