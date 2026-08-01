# Progress — Daily-rhythm expansion: forecast/outage capture + honest news

Supervised. Max 12 iterations. ONE task = ONE commit. Pause + report each. Never commit red; 3× red = blocked.
Maker ≠ checker: fresh-eyes subagent per task. Tests = temp dirs + DRY_RUN; live install = Mike handoff.
No deploy / no map-chart / no feature-eng / no harness changes this loop.

## Checklist
- [x] 0 — Setup: GOAL.md + PROGRESS.md; read CLAUDE.md (launchd rhythm + deploy); inspect ercot_catalog + archiver. ✔ done
- [x] 1 — INVENTORY (report only) → VERIFY_LOOP/INVENTORY.md. Probed retention live (t-365/t-730). ⏸ PAUSE for Mike. ✔ done
- [ ] 2 — Capture module (vintage-stamped, append-only, idempotent, per-file manifest).
- [ ] 3 — Backfill within retention; per-product files/span/disk/unknown-vintage counts.
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
