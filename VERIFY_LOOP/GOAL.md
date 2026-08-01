# GOAL — Expand the daily rhythm: (A) capture ERCOT's expiring forecast/outage products, (B) honest news

Capture the FUTURE TRAINING DATA (ERCOT's short-retention forecast + outage products) with full vintage
stamping, append-only, into the daily rhythm; plus honest news ingestion + a daily digest. Max 12
iterations, ONE task = ONE commit, pause + report each. Never commit red; 3× same red = blocked, stop.

## HARD CONSTRAINTS (violating any = RED)
1. **VINTAGE STAMPING IS THE WHOLE POINT.** Every captured forecast file records: product id, forecast
   TARGET period, publish/post time as reported by ERCOT, AND our capture timestamp (UTC). No vintage →
   store with `vintage=unknown` FLAGGED and COUNTED. Never synthesize/backdate/infer a missing vintage.
2. **Append-only archive.** Never overwrite a captured vintage; later revisions = additional vintages.
   Idempotent: re-running a capture never duplicates or mutates existing files.
3. **No LLM in the capture path.** News: headline + source + timestamp + link, dedupe by GUID/URL. ONE
   optional LABELED LLM pass may add relevance tags / ≤1-line summary, ALWAYS rendered WITH the link
   adjacent — never paraphrase with the source more than one click away.
4. **Inspection before assumption (the locational lesson).** Do NOT guess product IDs / retention —
   query the existing `ercot_catalog.py` SQLite (107 products) + the EMIL API to find them.
5. **Tests = temp dirs + DRY_RUN only.** Live enablement (launchd install/reload) is a FINAL handoff
   step for Mike, listed explicitly. jobs.jsonl logging + watchdog coverage + ntfy-on-failure for every
   new job — a silent capture failure is destroyed training data.
6. **No deploy, no map/chart work, no feature engineering, no harness changes in this loop.**

## VERIFICATION (maker ≠ checker, fresh-eyes subagent per task)
Captured files re-opened + schema-validated; one product's one-day capture cross-checked vs an
INDEPENDENT fetch path (query endpoint or MIS listing); vintage fields spot-checked vs ERCOT's own
posted timestamps; idempotency = run twice, byte-identical archive.

## TASKS
1. INVENTORY (report, no code): wind power production forecast, load forecast (system + zonal), solar/
   PVGR forecast, generation/transmission outage reports. Per product: ID, cadence, format, retention,
   availability vs 15:00 CT decision. Flag fastest-expiring. ⏸ STOP + show the table before building.
2. Capture module (forecast_store.py or extend ercot_archiver): pull each product on cadence into
   data_archive/forecasts/<product>/..., constraints 1-2 enforced, per-file manifest row (SQLite/jsonl).
3. Backfill what's still reachable inside each retention window. Report per-product: files, span, disk,
   unknown-vintage count.
4. Rhythm wiring: new launchd job(s) via the existing stub/dispatcher (prefer script edits over .app
   rebuild — FDA grant), jobs.jsonl rows, watchdog extended for missed cadence, ntfy on failure.
   DRY_RUN-tested; live install = handoff.
5. Independent verification pass: one day, one product, field-by-field vs an independent path; vintage
   timestamps vs ERCOT posted times.
6. News store: ERCOT market notices + EIA (+ obvious ERCOT RSS) polled on schedule into SQLite
   (constraint 3); /api/news read-only endpoint.
7. "Right now" sidebar news block (map tab): headlines + source + age + link, cap ~6, zero layout
   disruption, honest + calm. Headless screenshot; visual sign-off flagged for Mike.
8. Daily digest: evening ntfy (or new ~17:30 CT) — top headlines w/ links + capture health (products
   captured / misses). Templated; optional labeled LLM tag pass only.
9. Docs: CLAUDE.md forecast-archive section (products, cadences, vintage rules, disk growth) + news
   rules; PROGRESS.md final state.

## Env
`conda run -n volt`; ERCOT creds in `~/.zshenv` (non-interactive shells don't read .zshrc); respect the
existing archiver's rate/request patterns. Read CLAUDE.md (launchd rhythm + deploy rules) before agents.
When done: STOP with (a) live-enablement commands, (b) final inventory table, (c) disk-growth/month est.
Open-Meteo historical-forecast backfill + the feature loop through the harness are NEXT loops, not this.
