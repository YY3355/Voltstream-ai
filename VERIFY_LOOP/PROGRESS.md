# Progress — Daily-rhythm expansion: forecast/outage capture + honest news

Supervised. Max 12 iterations. ONE task = ONE commit. Pause + report each. Never commit red; 3× red = blocked.
Maker ≠ checker: fresh-eyes subagent per task. Tests = temp dirs + DRY_RUN; live install = Mike handoff.
No deploy / no map-chart / no feature-eng / no harness changes this loop.

## Checklist
- [x] 0 — Setup: GOAL.md + PROGRESS.md; read CLAUDE.md (launchd rhythm + deploy); inspect ercot_catalog + archiver. ✔ done
- [x] 1 — INVENTORY (report only) → VERIFY_LOOP/INVENTORY.md. Probed retention live (t-365/t-730). ⏸ PAUSE for Mike. ✔ done
- [x] 2 — forecast_store.py: vintage-stamped, append-only, idempotent, SQLite manifest. Verified:
      real capture (NP4-732 24 docs + NP1-346 snapshot) → re-run byte-identical (tree-sha unchanged,
      25=25 rows no dup); target span extracts (NP4-732 → +7day), honest none for snapshot; unk=0.
      Fresh-eyes subagent audit = 3/3 PASS (vintage/append-only/no-LLM). ✔ done
- [~] 3 — Backfill. PIVOT: archive per-day endpoint is ~0.5 docs/s HARD (server rate-limit; threaded
      w=4 gave NO speedup) → 227k docs = ~5 DAYS, dead. Switched to MONTHLY BUNDLES (a9c4553): one
      download/month, VINTAGE-FAITHFUL (bundle inner-filename postDatetime == archive postDatetime,
      6/6 to the second; bundle CSV byte-equals archive CSV; idempotent; archive-path regression
      clean). Bundles reach 2018 for most products. Inventory: 618 bundles, ~430k files, ~1.7GB,
      ~30-60min. Spans: wind/solar-sys/load-by-model/HRUC=2018-01; solar-region=2022-06; unplanned=
      2022-12; load-by-zone NP3-560 + trio = 2026-03 only (~4mo). Prior archive-doc backfill also
      committed (d4b6aad) — used for the recent unbundled tail. ⏸ awaiting Mike go to LAUNCH bundle
      backfill + tail decision (trio July tail = 288/day slow; defer to Task-4 daily job + July bundle).
- [x] 4 — Rhythm wiring. JOB=capture added to auto_commit.sh dispatcher -> auto_capture.sh (daily
      06:00 ET): archive-capture last CAPTURE_DAYS(=2) complete days ALL 11 products + bundle top-up,
      into gitignored data_archive/forecasts (commits nothing). jobs.jsonl row (job=capture), LOUD
      ntfy on failure / SILENT on success (digest covers it). watchdog_check.py extended: capture-
      freshness alert, GATED on capture-live so no false alarm pre-enablement. New plist
      com.voltstream.dartcapture.plist. DRY_RUN-tested offline (no ERCOT): dispatch+log+jobs.jsonl+
      notify all correct; watchdog 4 states pass (not-live/ok/stale/failed). Trio ongoing ~61MB/mo
      raw (~101MB 4KB-blocks), HIGH-8 ~50MB/mo — modest, trio ongoing OK to enable. Live install =
      Mike handoff (final). ✔ done (DRY_RUN)
- [~] 5 — Independent verification. CAUGHT the 66%-unknown bug (pre-2025 9-digit filename time vs my
      6-digit regex). Fixed: regex 6|9-digit; vintage_source + vintage_precision cols (mechanical gate);
      manifest-driven purge (deleted==expected==329,625, asserted, no glob); atomic write (tmp+replace,
      no partial files on disk-full). Post-fix: unknown=0, earliest 2018-01 for wind sys+region / solar
      sys / load-by-model. FRESH cross-check histogram: pre-2025 n=72 (84.7% exact, 100% within-1s, max
      1s); 2025+ n=96 (100% exact). BLOCKER: re-run hit DISK FULL (98%, NP3-565=4.1GB) — NP3-233 +
      NP1-346 pre-2025 incomplete; +1 orphan partial to clean. ⏸ Mike disk decision (trim NP3-565?) then
      complete the 2 products + re-verify. Code fix committed; archive completion is the ops step.
- [x] 6 — news_store.py: stdlib RSS 2.0 + Atom parse (no feedparser in volt), SQLite data_archive/
      news.db, dedupe by guid/URL (PK+INSERT OR IGNORE), NO LLM in store path (llm_model NULL);
      optional labeled enrich() reserved (summary/tags separate cols, always w/ link). /api/news
      read-only (TestClient 200, newest-first, llm=None). Fixture-verified: RSS+Atom parse, dedupe
      (re-ingest 0 new), undated item kept w/ NULL date (not fabricated). Live poll DEFERRED (ERCOT
      budget) — tiny live smoke of each source at enablement. Poll schedule wired in T8. ✔ done (fixtures)
- [x] 7 — "Right now" news block in the map sidebar (#news-now): reads /api/news, each row = headline
      (linked, target=_blank) + source + age, cap 6, HTML-escaped, 10-min refresh. Calm styling matching
      the briefing/layer-insight panels, zero layout disruption. Undated item shown w/o fabricated time.
      Headless screenshot verified renders (5 fixture headlines w/ source+age). ⏸ Mike visual sign-off.
      ✔ done (screenshot)
- [x] 8 — digest.py compose_digest (templated, NO LLM): top-N headlines (source+age+link adjacent,
      constraint 3) + capture-health line (latest capture jobs.jsonl row + docs-today + LOUD unknown-
      vintage flag -> ntfy priority high). auto_digest.sh (JOB=digest, 17:30 ET plist): news poll ->
      compose -> ONE ntfy push. Wires the T6 news poll schedule. JOURNAL_DIR seam added (capture+digest,
      no real-journal pollution in tests). DRY_RUN-tested: dispatch->compose->parse->notify->jobs.jsonl
      all correct, ASCII-clean. ✔ done (DRY_RUN)
- [ ] 9 — Docs (CLAUDE.md forecast-archive + news rules; PROGRESS final).

## Append-only log
- init (2026-08-01) — New capture/news loop from Mike's spec. Overwrote the Bolt-chart GOAL/PROGRESS.
  Next: read CLAUDE.md launchd rhythm + deploy rules; inspect ercot_catalog.py SQLite (107 products) +
  ercot_archiver + EMIL API; then Task 1 INVENTORY (report only, PAUSE before building).
- T0/T1 (2026-08-01) — Setup + inventory done. Probed live archive: hourly forecast/outage products
  (NP4-732/742, NP4-737/745, NP3-560/565/566, NP3-233, NP1-346) have ≥2yr retention (docs at t-730);
  intra-hour 5-min (NP4-751/752, NP3-562) are the fastest-expiring (<1yr, 0 docs at t-365). Vintage =
  postDatetime (publish) + row target period + our capture UTC — all three available. Format CSV-in-zip.
  Recommended HIGH set = 8 products. ⏸ PAUSED for Mike to confirm capture set before Task 2 builds.
- Set decision (Mike) — HIGH-8 ongoing+backfill; MED only if same code path (it is — generic), opt-in
  via capture-all MED, no heroics; intra-hour trio = backfill-all-now + DAILY batch (never 5-min),
  report disk/mo before enabling its ongoing job; NP1-346 lag_days=3 recorded in manifest; Task 3 to
  report per-product earliest reachable vintage.
- T2 (2026-08-01) — forecast_store.py built + verified + audited (3/3). Registry = HIGH-8 + PERISHABLE-3
  (PRODUCTS), MED-6 ridable (MED_PRODUCTS, opt-in). Idempotency proven byte-identical. commit next.
