# Progress — deepen on official ERCOT API (30d prices + constraints monitor)

- [done]  T0: cred check (NEW creds fresh-auth OK; OLD creds now FAIL)
- [todo]  T1a: NP6-905-CD 30-day backfill (background) -> ~30 cached days
- [done]  T1b: wire price_store to read NP6-905-CD archive-cache (schema adapter, dedup)
- [todo]  T2a: /api/constraints endpoint (today binding + recent bind counts)
- [todo]  T2b: Learning Lab constraints panel (concept vs reality, honest label)

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
