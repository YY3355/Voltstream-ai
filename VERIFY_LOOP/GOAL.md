# Goal
Retire the static-CSV crutch: wire price_store.py (rolling real-ERCOT price memory, shares
dart_cache/) as the platform's price source. Real recent prices feed every engine.

price_store API: cached_days()->[YYYY-MM-DD]; ensure_days(n)->(have,fetched,missing) fetches
missing complete past days into dart_cache; get_prices_rolling(hub,days=30,include_today=True,
fetch_missing=True,min_points=288)->(series,meta) raises RuntimeError if thin; meta["source"]
is the label. NB: get_prices_rolling calls ensure_days(fetch_missing=True) internally, so in
REQUEST paths pass fetch_missing=False to avoid a 20-min fetch inside a request.

## Tasks
- T1 BACKFILL: run ensure_days(30) once in background (~1 min/missing day; ~10 days cached now
  → ~20 missing). Verify cached_days() ~30 after. (Data op, no commit — dart_cache is gitignored.)
- T2 ercot_live.get_prices(): when LIVE_ON (ERCOT_LIVE!=0), try get_prices_rolling("HB_HOUSTON",
  days=30, fetch_missing=False) FIRST → set _cache["src"]=meta["source"]; else existing live pull;
  else CSV. ERCOT_LIVE=0 still forces CSV path unchanged (gate stays `if LIVE_ON`). data_source()
  surfaces meta["source"].
- T3 ercot_data.load_prices(): use store when PRICE_STORE!="0" AND ERCOT_LIVE!="0" — try
  get_prices_rolling(TARGET, days=30, include_today=False, fetch_missing=False) first, fall back
  to CSV dir. (include_today=False → only complete 96-pt days for rt/risk/qse per-day logic.)
  Coupling to ERCOT_LIVE!=0 makes ERCOT_LIVE=0 a clean offline switch → regression guard holds
  end-to-end with the specified test command. FLAG this design choice at check-in.
- T4 app.py startup pre-warm thread: also call price_store.ensure_days(30) (backfill + daily
  maintenance), before run_dart().

## Verify (per CLAUDE.md recipe; volt env; kill stale :8020; warm dart+risk)
- MAIN (NO ERCOT_LIVE=0): ERCOT_DATA_DIR=data_clean conda run -n volt uvicorn app:app :8020
  → /api/state 200 with data source = rolling-store label AND target_date RECENT (this month
    2026-07, NOT May). All 12 endpoints 200. Render each tab (hash deep-links) → panels populate.
- REGRESSION (WITH ERCOT_LIVE=0): restart; /api/state 200; source = "cached ERCOT CSVs";
  target_date = May (CSV data); all endpoints 200. Confirms CSV path unchanged.

## Guardrails
- Supervised. Max 12 iterations. One task = one commit. Never commit a broken panel.
- First /api/state after a cold start may take ~55s (today live fetch) — use long curl timeouts.
