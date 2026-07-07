# Progress — deepen on official ERCOT API (30d prices + constraints monitor)

- [done]  T0: cred check (NEW creds fresh-auth OK; OLD creds now FAIL)
- [done]  T1a: NP6-905-CD 30-day backfill (background) -> ~30 cached days
- [done]  T1b: wire price_store to read NP6-905-CD archive-cache (schema adapter, dedup)
- [done]  T2a: /api/constraints endpoint (today binding + recent bind counts)
- [done]  T2b: Learning Lab constraints panel (concept vs reality, honest label)

## Notes
- archive-cache schema (NP6-905-CD): DeliveryDate, DeliveryHour(1-24), DeliveryInterval(1-4?),
  SettlementPointName, SettlementPointPrice. Must verify ts construction vs a gridstatus day.
- dart_cache has gridstatus RT days 06-25..07-06; backfill adds deep days 06-07..06-24.
- Creds now in ~/.zshrc (rotated). Load from env; if non-interactive shell lacks them, use zsh -ic.

## Log
- T0 done: creds in ~/.zshenv (I wrote it), fresh token OK (len 1068), no inline creds.
- T1b done: price_store adapter (_api_frame_to_series M1 + postDatetime dedup) + get_prices_rolling
  merges gridstatus + archive days. CROSSCHECK 06-30: 95 intervals, max abs diff $0.0000, 100%
  match vs gridstatus. Merged series monotonic/no-dupes; load_prices recent July. commit below.
- T1a done (fast path): backfill_prices_to_cache(30) via query endpoint -> 30 days in ~2.6s.
  MAIN verify: /api/state source "rolling store (10 gridstatus + 30 archive days + today)",
  target 2026-07-05 (recent), all 13 endpoints 200 (dart slow-cold but 200 once warm, 0.012s).
  Regression ERCOT_LIVE=0 -> cached CSVs / 2026-05-18. Pre-warm now uses the fast backfill
  (dropped the wasteful ensure_days(30) that retried unavailable deep days).
- T2 done: /api/constraints (NP6-86-CD live) -> 11 binding today, top SEA_AAT1 $2044.80;
  Learning Lab panel renders beside toy DCOPF (concept vs reality), honest "not a grid model" label.
- Follow-up: NP6-86-CD constraint backfill via query endpoint (shdw_prices_bnd_trns_const):
  backfill_constraints_to_cache(14) wired into pre-warm. 14 days in ~77s. /api/constraints
  cached_days 15, bind-frequency now real (NUECES_WHITE_2_1 bound 5d).
