# Progress — deploy VoltStream to Fly.io

- [done]    T0: fresh-clone test (clean venv, pip install, live-mode boot)
- [todo]    T1: Dockerfile + fly.toml + 1GB volume at /data
- [blocked] T2: secrets + deploy  (BLOCKED: flyctl not authed in this shell)
- [todo]    T3: verify public https end-to-end + volume persistence
- [todo]    T4: README live URL, commit+push

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
