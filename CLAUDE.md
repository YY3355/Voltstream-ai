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

## launchd auto-commit (the COMMIT leg only — settle/report stay MANUAL)

The `commit` leg is automated by a **launchd agent** (`com.voltstream.dartcommit`) that runs daily
at **16:00 ET** (DA posts ~14:30 ET; 16:00 = safe margin). launchd, NOT cron, because launchd runs a
MISSED job on wake if the Mac was asleep. **`settle` + `report` are the judgment leg and stay manual.**

- **`scripts/auto_commit.sh`** — the logic (versioned source of truth): `cd` repo →
  `conda run -n volt python dart_journal.py commit` → if output says "already committed" exit 0 (a
  manual run earlier that day is fine, no dup) → else `git add journal && git commit -m "DART calls
  (auto) <tomorrow>" && git push` (push uses the osxkeychain cred). All output + a timestamp is
  appended to `journal/auto.log` (gitignored via `*.log`). Full tool paths + explicit exit codes
  (no `set -e`) because launchd has a minimal env.
- **The TCC catch (important):** a launchd-spawned process is denied access to `~/Documents` by
  macOS TCC — git/python against the repo fail with **"Operation not permitted"** (exit 126 / EPERM).
  Fix = a **targeted Full Disk Access grant**, NOT a broad grant to `/bin/bash`. Two catches drove the
  design: the FDA picker won't accept a bare `.sh`, AND a shell-script bundle executable is attributed
  by TCC to `/bin/bash` (so the `.app`'s grant wouldn't apply). So the job is a signed `.app` with a
  **compiled** executable:
  - **`~/Library/Application Support/VoltStream/DartAutoCommit.app`** — an ad-hoc-signed bundle whose
    executable `Contents/MacOS/dart_auto_commit` is a tiny **compiled Mach-O stub**
    (`scripts/dartcommit_stub.c`) that just runs `/bin/bash scripts/auto_commit.sh` and returns its exit
    code. A real binary gets the bundle's FDA grant; the bash/git/python it spawns inherit it.
    `auto_commit.sh` stays the single source of truth. Built by **`scripts/install_dartcommit_app.sh`**
    (compiles the stub + ad-hoc signs) from `scripts/dartcommit_stub.c` + `scripts/DartAutoCommit-Info.plist`.
  - The plist runs the bundle's executable **directly**, so macOS attributes the FDA grant to
    `DartAutoCommit.app` alone.
  - **You must grant it Full Disk Access:** System Settings → Privacy & Security → Full Disk Access →
    `+` → select `~/Library/Application Support/VoltStream/DartAutoCommit.app` (a `.app` selects
    normally). Without this, the job loads fine but every run fails "Operation not permitted".
  - **Rebuilding re-signs → invalidates the FDA grant** (new cdhash), so after any
    `install_dartcommit_app.sh` run you must remove the stale FDA entry and re-add the `.app`. Editing
    only `auto_commit.sh` needs NO rebuild (the stub runs it live) and keeps the grant.
- **Plist:** `~/Library/LaunchAgents/com.voltstream.dartcommit.plist` (reference copy
  `scripts/com.voltstream.dartcommit.plist`). `StartCalendarInterval` Hour 16 Minute 0 (Mac is in
  `America/New_York`, so Hour=16 == 16:00 ET), `RunAtLoad false`.
  - Manage: `launchctl bootstrap gui/$(id -u) <plist>` / `bootout` / `kickstart -k
    gui/$(id -u)/com.voltstream.dartcommit` (kickstart = run now). After editing `auto_commit.sh`,
    no reinstall needed (launcher sources it); after editing the launcher, re-copy it to `~/Library`.
  - Logs: `journal/auto.log` (the run log) + `journal/launchd.{out,err}.log` (launchd-level; catch
    TCC/pre-exec failures). All gitignored.
