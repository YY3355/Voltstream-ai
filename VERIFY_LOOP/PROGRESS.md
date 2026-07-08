# Progress — deploy VoltStream to Fly.io

- [done]    T0: fresh-clone test (clean venv, pip install, live-mode boot)
- [done]    T1: Dockerfile + fly.toml + 1GB volume at /data
- [done]    T2: secrets + deploy  (BLOCKED: flyctl not authed in this shell)
- [done]    T3: verify public https end-to-end + volume persistence
- [done]    T4: README live URL, commit+push

## Notes
- Cache dirs already env-driven (DART_CACHE_DIR/PRICE_CACHE_DIR/ARCHIVE_DIR) -> no code change for /data.
- Fresh-clone risk: no CSVs -> live mode; get_prices tries rolling store (fetch_missing=False) ->
  if archive-cache empty (pre-warm not done) -> single-day live (71 pts) -> compute_state full[] empty
  -> /api/state 500. Watch for this cold-start race in T0.
- flyctl at ~/.fly/bin/flyctl; NOT authed (no token in config.yml / env).

## Log
- T0 fixes: requirements.txt +gridstatus +requests (were missing -> live pull failed in clone;
  gridstatus also pins pandas<3). price_store.get_prices_rolling backfill_if_thin (cold-start
  query-endpoint populate). ercot_live.get_prices include_today=False (skip ~46s gridstatus
  today-fetch on landing) + backfill_if_thin. ercot_data.load_prices backfill_if_thin + empty
  guard (no more "No objects to concatenate" on absent data_clean). app.py forecast train-window
  cap (FORECAST_TRAIN_DAYS=10). Clone boot: /api/state 46s->1.5s, live rolling store, target 2026-07-07.
- T0 VERIFIED from a FRESH LOCAL clone (cdc92d0, clean venv, no data_clean): app boots live;
  /api/state 200 @1.5s (source "rolling store (30 archive days, real ERCOT)", target 2026-07-07);
  all core endpoints + risk 200; journal real ledger (n_days 1, -$36.86, 40.5%); dart 200 once
  warm (cold gridstatus fetch slow, unchanged). Label honesty fix confirmed (no "+ today").
- Pre-existing Dockerfile/fly? repo already has Dockerfile + docker-compose.yml + main.py + api/
  core/ agents/ dirs — must inspect Dockerfile in T1 (may need to align to app:app).
- T2 done: secrets staged via stdin pipe (no values in transcript), ANTHROPIC NOT set; deployed
  app voltstream-ercot (dfw, shared-cpu-1x/1gb, volume /data). Live: https://voltstream-ercot.fly.dev
- T3 done: all 13 endpoints 200 (dart cold 294s on shared CPU); every tab renders on the public URL;
  paper-book real ledger (n_days 1, -$36.86, 40.5%, not $0.00); constraints live (2026-07-08, 40
  binding, SEA_AAT1); About + honest labels; answer_mode "grounded template" (no LLM spend).
  Volume persistence: 45 archive + 10 dart files survived restart; dart 294s->60s(2nd boot)->0.11s
  (warm). Steady-state state 2.6s / dart 0.11s. First-boot window ~1min (pre-warm today-fetch on shared CPU).
