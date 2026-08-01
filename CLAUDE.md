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

## Deploying to Fly (EXPLICIT-GO ONLY — never the loop's initiative)

- **Deploy happens only on Mike's literal go.** No agent/loop ever runs `fly deploy` on its own
  initiative — not "when green", not "to be helpful". Mike says "deploy" (or "signed off, deploy");
  until then, a finished loop STOPS with screenshots + the sign-off checklist, nothing shipped.
- **Redeploy to the EXISTING app only** (`voltstream-ercot`, region dfw). NEVER create Fly resources —
  no new machines/volumes/regions/scale changes. `fly deploy --remote-only` (remote depot builder;
  fly.toml already points at `Dockerfile.fly`). Local git push is not required for deploy (fly tars the
  working dir, respecting `.dockerignore`) but push anyway to keep origin in sync. Move scratch dirs
  OUT of the repo first — `*.py/*.html/*.png` under the working dir would otherwise be tarred into the image.
- **The pre-deploy gate: fresh-clone / Docker-image build + run + curl.** Before any deploy, prove the
  COMMITTED state actually serves: build the image, run the container, curl every endpoint. **CONTAINER-
  RUNTIME GAP (important):** no `docker`/`podman`/`nerdctl`/`finch` is installed, so the literal Docker
  gate CANNOT run. The v20/v21 ships used an intent-verification SUBSTITUTE — a fresh `git clone` booted
  under the `volt` env, endpoints curled, plus a check that the changed files ship and no new snapshot
  `.json/.csv` slipped in — which Mike explicitly accepted as a stand-in. **To make the gate REAL instead
  of ceremonial, install colima before the next deploy:** `brew install colima docker && colima start`,
  then the Docker build+run+curl gate actually executes. The runtime is the teeth; this rule is the paper.
- **Committed-artifact snapshot rule.** Fly's volume is ephemeral and caches don't ship, so anything the
  live app reads at runtime must be COMMITTED to the repo AND survive `.dockerignore` (which excludes
  `*.json`/`*.csv` by default). Whitelist it (`!clim_result.json`, `!band_*.json`, …) or the fresh
  clone / Fly image silently serves a stale-or-missing artifact (e.g. a bandless chart). This is the
  exact snapshot bug the `*_result.json` / `band_*.json` committed-artifact pattern exists to prevent.

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

## launchd daily rhythm (commit + settle automated; report stays MANUAL)

Three launchd agents run the DART book's daily rhythm. **`report` is the only manual leg** (the
judgment call — Mike reads it). launchd, NOT cron, because launchd runs a MISSED job on the next
wake if the Mac was asleep. All times are local ET (Mac TZ = `America/New_York`), logged UTC+local.

| Agent | When (ET) | JOB | Script | Does |
|---|---|---|---|---|
| `com.voltstream.dartcommit`   | 16:00 | (unset→commit) | `auto_commit.sh` | commit+push tomorrow's calls |
| `com.voltstream.dartsettle`   | 09:00 | `settle`        | `auto_settle.sh` | catch-up settle past days, commit+push ledger |
| `com.voltstream.dartwatchdog` | 18:30 | `watchdog`      | `watchdog.sh`    | health check; alert if the rhythm broke |
| `com.voltstream.dartcapture`  | 06:00 | `capture`       | `auto_capture.sh`| capture prior day(s) + bundle top-up into `data_archive/forecasts` (disk-guarded) |
| `com.voltstream.dartdigest`   | 17:30 | `digest`        | `auto_digest.sh` | poll news + send the evening digest push |

- **One `.app`, five jobs — the dispatcher.** All agents run the SAME FDA-granted stub
  (`DartAutoCommit.app`, which execs `/bin/bash scripts/auto_commit.sh`). `auto_commit.sh`'s header
  dispatches on the **`JOB`** env var (set in each agent's plist `EnvironmentVariables`): unset→commit,
  `settle`→`exec auto_settle.sh`, `watchdog`→`exec watchdog.sh`, `capture`→`exec auto_capture.sh`,
  `digest`→`exec auto_digest.sh`. `environ` passes through the compiled stub, and `exec` stays under the
  .app's TCC grant — so **adding a job needs NO .app rebuild, NO FDA re-grant**, only a new plist + shell
  script. (Prefer this over rebuilding the stub. The capture + digest legs were added this way.)
- **Jobs & helpers** (all in `scripts/`): `auto_commit.sh` (commit leg + dispatcher entry),
  `auto_settle.sh` (settle leg, pure arithmetic — NO LLM), `watchdog.sh`+`watchdog_check.py` (health),
  `notify.sh` (ntfy.sh push), `joblog.sh` (sourced: `emit_job_row`). Each job resolves siblings via an
  absolute `SCRIPT_DIR` (captured before it `cd`s away), writes UTC+local log lines, and (via an EXIT
  trap) one structured row to **`journal/jobs.jsonl`** (gitignored): `{job, asof_date, started, ended,
  status, error, commit_sha}`. No `set -e` — exit codes are explicit and the trap always logs.
- **Notifications** (`notify.sh`): commit-push success (date + n calls), settle success (days + P&L
  delta + cumulative), and ANY failure (loud, `high` priority, from the trap). Set **`NTFY_TOPIC`** to
  a ntfy.sh topic to turn them on (unset = silent no-op). `DRY_RUN=1` prints instead of sending.
  notify.sh is best-effort — it can never fail a job.
- **Provenance / regime:** every auto calls file is stamped `model_version` (git blob SHA of the
  signal-logic files `dart_journal.py`+`dart_engine.py`), `generated_by:"auto"`, `generated_at` (UTC).
  Regime = manual ≤2026-07-22, auto ≥2026-07-24; history is never rewritten (see README "Ledger regime").
- **Env seams (tests NEVER touch the real book):** `CODE_DIR` (python cwd / real signal files),
  `JOURNAL_REPO` (git tree the journal lives in), `JOURNAL_REMOTE` (push target), `JOURNAL_DIR`
  (python journal path), `DART_ASOF` (injectable "now", never backdates), `DART_FIXTURE` (realized-DART
  CSV → no network). A **hard guard** refuses (`exit 3`) if `DART_FIXTURE` is set but the repo is the
  real one. Test harness: `tests/mk_temp_journal.sh` (temp journal repo + bare remote + faithful
  .gitignore), `tests/seed_calls.py` + `tests/fixtures/dart_hist.csv` (each settled day = +$7.00).
  Verify a job in a temp env, e.g.:
  ```bash
  eval "$(bash tests/mk_temp_journal.sh)"
  CODE_DIR="$PWD" JOURNAL_REPO="$WORK" JOURNAL_REMOTE="$BARE" DART_ASOF=2026-07-22 \
    DART_FIXTURE="$PWD/tests/fixtures/dart_hist.csv" DRY_RUN=1 NTFY_TOPIC=t bash scripts/auto_commit.sh
  ```
- **Scheduling caveat:** launchd only fires while the Mac is awake/on. `StartCalendarInterval` re-runs
  a missed job on the next wake, but a multi-day laptop-off stretch = missed days BY DESIGN (a commit
  after its window logs a MISSED day, never backdates). Always-on (Fly) is the future fix.
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
- **Plists:** reference copies in `scripts/com.voltstream.dart{commit,settle,watchdog}.plist`; installed
  copies in `~/Library/LaunchAgents/`. Each is `StartCalendarInterval` (local ET) + `RunAtLoad false`;
  settle/watchdog add `EnvironmentVariables.JOB`. Install a new one:
  ```bash
  cp scripts/com.voltstream.dartsettle.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.voltstream.dartsettle.plist
  ```
  - Manage: `launchctl bootstrap gui/$(id -u) <plist>` / `bootout gui/$(id -u)/<label>` /
    `kickstart -k gui/$(id -u)/<label>` (kickstart = run now). Editing a `scripts/*.sh` needs NO
    reinstall (the stub runs them live); only rebuilding the `.app` needs a re-grant.
  - Logs (all gitignored): `journal/auto.log`, `settle.log`, `watchdog.log`, `capture.log`,
    `digest.log` (per-job run logs); `journal/jobs.jsonl` (structured rows);
    `journal/launchd.{out,err}.log` (launchd-level).

## The forecast/outage archive (`forecast_store.py`) — the future training data

Vintage-stamped, append-only capture of ERCOT's forecast + outage products (the decision-time-clean
inputs the feature loop will train on) into `data_archive/forecasts/<EMIL>/<post-date>/<postDtCompact>__<docId>.{zip,csv}`
+ a SQLite index `manifest.db`. All gitignored — the archive lives on disk like `dart_cache/` (the
launchd rhythm runs locally). ~495k docs, deep to 2018-01 for most products.

- **Products.** HIGH-8 (feature ingredients): wind `NP4-732`/`NP4-742`, solar `NP4-737`/`NP4-745`, load
  `NP3-560`/`NP3-565`, outage `NP3-233` (HRUC) + `NP1-346` (unplanned). Intra-hour trio (perishable,
  <1yr retention, ~120d): `NP4-751`/`NP4-752`/`NP3-562`. MED-6 ride the same path (opt-in via
  `capture-all MED`). `NP1-346` is a **3-day-lagged snapshot** (`lag_days=3` in the manifest) — a lagged
  input at decision time, NEVER a forward forecast; the feature loop's available_at gate must honor it.
- **Two capture paths, one store.** (1) Monthly **bundles** (`backfill_bundles`) — one download per
  month, reaching back to **2018** (far past the per-day archive's ~2yr retention); the primary backfill.
  (2) The per-day **archive endpoint** (`capture_product`) for the recent unbundled tail —
  rate-limited to **~0.5 doc/s** (server-bound; concurrency does NOT help), so it is only for the
  ~1-month tail, never bulk. Both share `_store_doc` → identical vintage-stamp + append-only +
  idempotency; a doc seen by either path resolves to the same on-disk path (cross-method idempotent).
- **VINTAGE IS THE POINT (admissibility).** Every doc records product id + forecast target period +
  ERCOT's post time + our capture UTC. The post time is ERCOT's own per-file timestamp embedded in the
  archive filename. Cross-checked against the archive endpoint's `postDatetime` (n=72 pre-2025, n=96
  2025+): exact to the second for 100% of 2025+ docs and 85% of pre-2025 docs, and within 1 second in
  100% of cases (max observed offset 1s). For pre-2024 history — which predates the archive endpoint's
  ~2-year retention and thus has no `postDatetime` to compare against — it is the sole ERCOT-reported
  post time, carried with `vintage_precision='within_1s'`. **A ≤1s vintage error is immaterial for
  hourly products consumed at a 15:00 CT daily decision.** (The 9-digit pre-2025 filename time carries
  millis; 6-digit 2025+ is HHMMSS and matches `postDatetime` exactly.) Columns: `vintage_source` ∈
  {`archive_postDatetime` (exact), `bundle_filename`}, `vintage_precision` ∈ {`exact`, `within_1s`} — the
  feature loop gates on precision MECHANICALLY, not by reading docs. A missing post time is stored
  `vintage_status='unknown'`, FLAGGED + COUNTED, never synthesized (target 0; currently 0).
- **Append-only + idempotent + no-LLM.** Never overwrite a vintage; a later revision = a new docId = an
  additional vintage. Idempotency = skip-seen by docId + `INSERT OR IGNORE` (doc_id PK) + atomic write
  (tmp + `os.replace`, so a disk-full / interrupted write never leaves a truncated file). Re-run is
  byte-identical. NO LLM anywhere in the capture path. `purge-unknown` is manifest-driven + asserts
  `deleted+missing == expected` (no glob deletion in the archive).
- **Disk + the guard.** ~7.6 GB (NP3-565 load-by-model alone ~4 GB — its all-models × weather-zone CSVs
  are huge; do NOT trim its depth — load is the #1 price driver). Ongoing daily capture ~110 MB/mo (trio
  ~61 MB/mo raw). **Disk guard:** `auto_capture.sh` skips-and-alerts when free < `FORECAST_MIN_FREE_GB`
  (default 10) so the trading rhythm's commit/settle git writes never fail on a full disk; the watchdog
  alerts on low disk. `ARCHIVE_DIR` relocates the whole archive (e.g. to an external volume) with one env
  var. zstd recompression was tested and REJECTED (per-doc 1.08x / batched 1.51x — ERCOT's per-doc zips
  already deflate the CSVs ~2.5x); relocation is the disk fix, not compression.
- **CLI:** `capture-recent-days N [TIER]`, `backfill-bundles[-all] [TIER]`, `capture[-all]`, `report`
  (per-product files / earliest vintage / disk / precision), `purge-unknown`, `reindex`.

## News + daily digest (`news_store.py`, `digest.py`)

- **News store.** Stdlib RSS 2.0 + Atom (no feedparser in `volt`) → `data_archive/news.db`, deduped by
  GUID/URL (PK + `INSERT OR IGNORE`). The store path is pure: headline + source + timestamp + link, **NO
  LLM** (`llm_model` stays NULL). An optional labeled `enrich()` may add a ≤1-line summary / tags in
  SEPARATE columns, always rendered WITH the link adjacent — never a paraphrase with the source more than
  one click away. Unparseable feed dates → `published_utc` NULL + raw kept (flagged, never fabricated).
  `/api/news` is read-only; the map sidebar `#news-now` block renders it (cap 6, calm, source+age+link).
  `SOURCES` (EIA + ERCOT notices) URLs are confirmed at enablement; the live poll is a launchd step.
- **Digest.** `digest.py compose_digest` builds a TEMPLATED evening push (top headlines w/ links +
  capture-health line: latest capture status + docs-today + a LOUD unknown-vintage flag → ntfy priority
  high). NO LLM in the compose. `auto_digest.sh` (JOB=digest, 17:30 ET) polls news → composes → one ntfy
  push; this also drives the news poll schedule. `JOURNAL_DIR` seam keeps tests off the real journal.
