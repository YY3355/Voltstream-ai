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
- [ ] 4 — Rhythm wiring (launchd via stub dispatcher, jobs.jsonl, watchdog missed-cadence, ntfy). DRY_RUN.
- [ ] 5 — Independent verification (one product/day field-by-field + vintage vs ERCOT posted).
- [ ] 6 — News store (ERCOT notices + EIA + RSS -> SQLite) + /api/news read-only.
- [ ] 7 — "Right now" sidebar news block (map tab), cap ~6, calm. Screenshot; Mike visual sign-off.
- [ ] 8 — Daily digest (evening ntfy: headlines + links + capture health). Templated + optional LLM tag.
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
