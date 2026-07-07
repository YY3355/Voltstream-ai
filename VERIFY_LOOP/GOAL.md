# Goal
Deepen the platform on the official ERCOT API (archiver already built): real 30-day price
history + a live binding-constraints monitor paired with the toy DCOPF.

## Tasks
- T0 CRED CHECK: archiver authenticates with the NEW rotated creds (now in ~/.zshrc) via a
  FRESH token fetch; the OLD creds must now FAIL. (Runtime check, no commit.)
  NB: non-interactive shells may NOT source ~/.zshrc — if env is empty, use `zsh -ic '...'`
  or `source ~/.zshrc` so creds load; never paste creds inline (they're rotated/secret now).
- T1a BACKFILL (background): ercot_archiver.ensure_days("NP6-905-CD", 30) -> 30 days of RT
  settlement-point prices into data_archive/archive_cache/ (throttled, 429 backoff). Verify
  ~30 cached days after.
- T1b WIRE price_store: teach price_store to also assemble the hub series from the NP6-905-CD
  archive-cache (ERCOT-API schema: DeliveryDate/DeliveryHour/DeliveryInterval + SettlementPoint
  Name/SettlementPointPrice -> 15-min HB_HOUSTON series), merged+deduped with the existing
  dart_cache gridstatus days. get_prices_rolling should report ~30 real days. VERIFY timestamp
  construction against an overlapping gridstatus day before trusting it. Commit.
- T2a ENDPOINT: /api/constraints -> today's SCED binding constraints from NP6-86-CD (name,
  shadow price, sorted by severity) + "how often each bound recently" count over cached days.
  Verify curl live. Commit.
- T2b PANEL: new Learning Lab panel beside toy DCOPF. Concept (3-bus toy) vs reality (today's
  actual grid). Honest label: reads real constraint data, NOT a grid model (no topology, no
  shift factors). Verify live + tab render. Commit.

## Verify (CLAUDE.md recipe)
- volt env; kill stale :8020; warm dart+risk before rendering.
- Store deepening: start WITHOUT ERCOT_LIVE=0 -> /api/state source shows expanded store
  (~30 cached days) + RECENT target_date; all 12 endpoints 200.
- Regression: ERCOT_LIVE=0 still -> cached CSVs / May (unchanged).
- Constraints panel: /api/constraints returns real constraint names + shadow prices; render
  /#learning -> both DCOPF and the new constraints panel populate.

## Guardrails
- Supervised. Max 12 iterations. One task = one commit. Never commit a broken panel.
- Creds are secret (rotated) — load from env/~/.zshrc, never inline in a command.
