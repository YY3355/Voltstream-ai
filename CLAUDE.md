# VoltStream — working notes for Claude

Agentic co-pilot demo for ERCOT battery trading. FastAPI backend (`app.py`) serves a
single-page dashboard (`dashboard_live.html`) with a top nav and six sections (Co-Pilot,
Asset Optimization, Trading Desk, Quant & Structuring, Learning Lab, About). Each engine
module has a `/api/*` endpoint and a panel; heavy tabs lazy-load on first open.

## Running the server (READ THIS FIRST)

The project runs in the **`volt` conda env**, NOT base. The base anaconda env has a
cvxpy/numpy clash that stops the server importing (`cooptimize` → cvxpy). Always:

```bash
ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
```

- **`ERCOT_LIVE=0` is REQUIRED.** Without it, `get_prices()` does a live pull (~71 pts, less
  than one full day) and `/api/state` 500s (`full[-1]` on an empty list). This breaks every
  CSV-backed panel (forecast, co-optimization, VPP, RT). With `ERCOT_LIVE=0`, those read the
  cached real-ERCOT CSVs in `data_clean/`.
- **DART is independent of `ERCOT_LIVE`.** `dart_engine.fetch_live()` hits gridstatus
  directly, so the DART panel is live in either mode. Its first cold pull is slow (~400s: the
  RT 15-min report is ~55s/day); results are disk-cached in `dart_cache/` (gitignored) and
  pre-warmed on startup, so restarts are fast.
- **Kill any stale listener first**, then wait for the NEW instance — a leftover uvicorn on
  :8020 answers new routes with 404s and wastes a debug cycle. `conda run` buffers stdout, so
  an empty server log does NOT mean it failed to start; trust the port, not the log:
  ```bash
  lsof -ti tcp:8020 | xargs kill -9 2>/dev/null; sleep 1
  # then poll for readiness:
  until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8020/openapi.json)" = 200 ]; do sleep 1; done
  ```

## Verifying a change

1. **Warm the heavy caches before rendering** so page loads don't time out:
   ```bash
   curl -s --max-time 120 -o /dev/null -w 'dart %{http_code} %{time_total}s\n' http://127.0.0.1:8020/api/dart
   curl -s --max-time 60  -o /dev/null -w 'risk %{http_code} %{time_total}s\n' http://127.0.0.1:8020/api/risk
   ```
   (`risk` runs Monte Carlo, ~15s; `dart` cold ~400s / warm instant.)
2. **Curl every endpoint, expect 200**: `state, cooptimize, vpp, rt, curve, swap, risk, qse,
   dart, dcopf, journal` (GET) and `ask` (POST). Independently assert sane numbers — separate
   the maker from the checker.
3. **Render each tab in headless Chrome** and confirm its panels populate. Sections are
   deep-linkable by hash, so each tab renders independently:
   ```bash
   CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
   "$CHROME" --headless=new --disable-gpu --no-sandbox --virtual-time-budget=16000 \
     --dump-dom "http://127.0.0.1:8020/#trading" > dom.html      # or --screenshot=page.png
   ```
   Tabs: `/` (Co-Pilot), `/#assetopt`, `/#trading`, `/#quant`, `/#learning`, `/#about`.
   Lazy-load check: on `/`, the heavy panel heroes (`#dart-hero`, `#risk-hero`, `#coopt-hero`,
   …) must still be EMPTY — no loader fires for an unopened tab.
   (No playwright/PIL installed; Chrome.app is present. Long-running server + curl should run
   as background Bash tasks — a foreground shell has a 2-minute wall that kills stacked
   startup+fetch.)

## Adding a new engine as a panel (the recurring pattern)

1. **Source the module** — usually dropped in `~/Downloads`; copy it in:
   `cp "$(ls -t ~/Downloads/<name>*.py | head -1)" <name>.py`. Read it to get the exact
   return shape before wiring.
2. **Endpoint** in `app.py`: `@app.get("/api/<name>")` calling the module's top-level function,
   wrapped in `try/except` returning `{"error": ...}` — mirror the existing engine routes.
   Commit the endpoint + the new module together.
3. **Panel** in `dashboard_live.html`: add a `<div class="card lit" id="c-<name>">` inside the
   right `<section>`, numbered sequentially within that section, plus an `async function
   <name>()` renderer (inline SVG charts; fonts IBM Plex Mono; palette cyan `#22d3ee`, blue
   `#58a6ff`, amber `#f0a35e`, red `#f85149`, green `#3fb950`). Register the loader in the
   `LOADERS` map (fires once on first tab open); read values from the API response — don't
   hardcode facts the data carries.
4. **Keep the module's honesty labels** in the panel note (e.g. "learning model, not
   calibrated", "congestion proxy, not nodal", "simulated telemetry, not a real QSE"). The
   About tab is the canonical honest-scope statement.
5. **Verify + commit** per above. One task = one commit; never commit a failing curl/render.

## Endpoints ↔ engines

`state`+`ask` → forecast_engine / battery_dispatch (Bolt) / copilot · `cooptimize`,`vpp` →
cooptimize / vpp · `rt` → rt_engine · `curve`,`swap` → forward_curve · `risk` → risk_engine ·
`qse` → qse_loop · `dart` → dart_engine (live) · `dcopf` → dcopf · `journal` → journal/ledger.csv
(DART paper book; honest empty state until the first settlement).

## The DART paper book

`dart_journal.py`: `commit` writes tomorrow's calls to `journal/calls_<date>.json` (git-commit
same day — the git history is the audit trail, no hindsight); `settle` scores past calls into
`journal/ledger.csv`; `report` summarizes. Not live trading: virtual fills at settlement, no
execution/fees/risk limits. `journal/` IS tracked in git (the audit trail); `dart_cache/` is not.
