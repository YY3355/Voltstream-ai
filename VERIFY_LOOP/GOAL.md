# Goal
Wire dart_engine.py into the app as panel 12 — "DART Spreads & Congestion (live)".
(dart_engine.py copied in from ~/Downloads, same pattern as risk_engine/qse_loop.)

run_dart(days=5) fetches LIVE ERCOT via gridstatus (DA hourly + RT 15-min, Trading Hubs).
Takes NO data_dir. Returns either an error dict {"error": ...} OR:
  hubs[], ref_hub, data_source (starts "LIVE ..."),
  stats: {HUB: {mean, std, hit_rate_pct, n_hours, cum_1mw}}
  hod_profile: [{hour, dart}]  (ref hub hour-of-day DART bias)
  basis: {"WEST-NORTH"/"HOUSTON-NORTH"/"SOUTH-NORTH": {mean, std, last, max_abs}}
  series: {ts[], da[], rt[], dart[]}  (ref hub, last ~72h)
  basis_series: [] (RT West-North basis over same window)
  window: {start, end, hours}

## Definition of done
1. `/api/dart` endpoint in app.py calls run_dart() (try/except like other routes).
2. Panel 12 in dashboard_live.html, house style, with:
   - hero: ref hub mean DART + hit rate
   - DA-vs-RT overlay chart with the DART spread beneath it
   - hour-of-day DART bias bars (hod_profile)
   - basis strip WEST-NORTH / HOUSTON-NORTH / SOUTH-NORTH, labeled
     "congestion proxy (hub basis) — real congestion analysis is nodal
      (DCOPF/shadow prices), not claimed here"
   - note: live ERCOT data via gridstatus

## How to verify (every iteration) — LIVE DATA, do NOT set ERCOT_LIVE=0
Project runs in `volt` conda env. Kill any stale :8020 listener first, then wait for
the NEW instance (200 on /api/state).
Start server:
    ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
Then:
    curl --max-time 120 http://127.0.0.1:8020/api/dart   (first call fetches several days DA+RT)
    LIVE CHECK: JSON.data_source startswith "LIVE"  AND  stats has >=3 hubs (non-empty).
    Then render http://127.0.0.1:8020/ via headless Chrome -> panel 12 populates.
    (warm /api/dart with curl FIRST so page render returns from cache fast; TTL 30min)
If the server subprocess lacks network (sandbox), rerun the server Bash with
dangerouslyDisableSandbox so gridstatus can reach ERCOT.

## Guardrails
- Supervised. Max 12 iterations.
- Never commit anything that fails the LIVE-data check (data_source must be LIVE, >=3 hubs).
  An {"error": ...} response = red = do not commit.
- One task per commit.
