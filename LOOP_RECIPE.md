# Loop: Structuring Desk + Desk Table (climatology baseline)

Supervised verify-loop, Opus, max 8 iterations, ONE task = ONE commit.
Env recipe as usual: `conda run -n volt`, `ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean`
for CSV mode, kill stale :8020, warm /api/dart + /api/risk before render checks,
headless-Chrome/CDP render per tab, screenshots for all visual tasks.

## Honesty contract for this loop (non-negotiable, echo in commit messages)
- Realized vol is labeled "realized, not implied — no option quotes available" everywhere it renders.
- Option values labeled "model value under realized vol — not a market quote."
- Desk table probability column is "Clim P(RT>DA)"; the word "Model" appears nowhere until the eval-harnessed model ships. model_p / load_fcst / wind_fcst render as "—".
- Cells with n < 30 samples render "—", never a number.
- No vol surface. No implied anything. No smoothing across (month,hour) cells.

## Tasks (in order)
1. **Drop in modules.** Copy vol_engine.py, options_engine.py, desk_climatology.py into repo root; run test_fixtures.py inside conda env. Green = commit. (Fixtures prove math on synthetic data only — say so in the commit message.)
2. **Wire vol to the real archive.** New endpoint `/api/vol?hub=&bucket=` reading price_store daily DA/RT series (peak = HE7–22 avg, offpeak = rest; declare the definition in the payload). Returns realized_vol for 20/60/250d + vol_cone. Verify: values are finite, n_obs matches archive length, excluded-day counts printed to log. Sanity: Houston normal vol should be same order as historical DART swings — if it comes out < $10 or > $10,000 per sqrt-yr, STOP and inspect, don't ship.
3. **Governed pricer endpoint.** `/api/option` — inputs: hub, month (delivery), strike, type, model policy. F comes from the existing bootstrapped forward curve (pass its version string through). vol from task 2 (caller picks window; window echoed in vol_source). If any monthly forward ≤ 0, black76 must return its refusal error to the UI verbatim; UI offers bachelier instead.
4. **Structuring panel in Quant tab.** ATM call/put card per hub for front month: value + Greeks + the provenance block (model_policy, vol_source, curve version, asof) rendered visibly, plus the vega tie-in line: link to existing Monte-Carlo battery vega result — "the battery is long exactly what this option prices." Screenshot required.
5. **Climatology build.** Script computes build_climatology per hub from the full archive, writes `clim_result.json` (committed snapshot, same pattern as decade/hedge — Fly volume caveat applies). Log total hours + date range; must match known archive span (2018-01 → present for SPP-derived series; if hourly RT/DA pairs only cover the rolling window, LABEL the range honestly in the payload — do not imply decade coverage the data doesn't have).
6. **Desk table tab/panel.** Per-hour table for today+tomorrow: DA price (real, from cache; "—" until DAM publishes), Clim P(RT>DA), clim DART q05/q50/q95, n, Your Call (from dart_journal if present), and the three reserved "—" columns with an ⓘ tooltip: "reserved for eval-harnessed forecast model / ERCOT forecast products — roadmap, not built." Column layout mirrors the per-MTU desk view pattern. Screenshot required.
7. **Fresh-clone test + Fly deploy.** Standard pattern; verify /api/vol, /api/option, desk table render on the deployed app (snapshot-bug lesson).

## Explicitly out of scope (do not let the loop drift into these)
Option taxonomy lists, barrier/Asian/swing pricers, implied vol, spark spreads
(no gas curve wired), any forecast model, any "Model P(up)" number.
