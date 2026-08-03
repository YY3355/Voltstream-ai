# Progress — Kardashev RT-DA spread forecast audit

Supervised. Max 8 iterations. ONE task = ONE commit. Pause + report each. Never commit red; 3x red = blocked.
No LLM in scoring. No harness/signal.py/deploy/UI. Independence = OUR stores are ground truth, never their API.

## Checklist
- [x] 1 — Fetch + freeze. API public (data.kardashevlabs.org, no auth). Froze snapshot_2026-08-02/ (15
        nodes, 21,555 recs, span 2026-07-08..08-02 ~25d, 27 issuances, 2 models, quantiles P10/P50/P90,
        0 untimely). manifest.json (per-file sha256 + fetch UTC). SCHEMA.md documents it. Scoreable = 4
        hubs (HB_HOUSTON/NORTH/SOUTH/WEST); 11 unscored (no verified coverage). Their spread = rt-da =
        -dart (prelim, PROVE in T2). ✔ done
- [x] 2 — Sign + alignment gate PROVEN (sign_gate.py, MAPPING.md): 26 hrs / 3 days / HB_HOUSTON, max
        |our_DA-their_da|=0.0000 + max|our_dart-(-their_spr)|=0.0000. dart = DA-RT = -(their spread);
        their [P10,P90]->dart [-P90,-P10]. tz: their ts=UTC hour-start, CDT=UTC-5. RT=NP6-905 (HE 1-24,
        4x15m), DA=dart_cache DAY_AHEAD (CDT hour-begin). Deep locational/dam_decade end ~07-01 (pre-
        window) -> window rides our gridstatus caches (still ours). ⏸ STOP — show Mike before scoring. ✔
- [x] 3 — Join + score (score.py). Realized spread=RT-DA from dart_cache (both, cent-validated). Per-
        model, baselines on each model's own coords, n beside every metric, dedup latest-issuance/hour
        (collapsed 2672 exact-dup rows), 120 unsettled excluded, untimely=0. RESULTS: tft-2026q3 n=1576
        pin_avg 1.789 cover 0.767; tft-v2 n=1380 pin_avg 2.224 cover 0.840. Both beat clim(2.19/2.30),
        zero(3.26/3.45), persistence(3.62/3.61). v1 sharper+under-covers, v2 wider+well-calibrated.
        CHECKER (independent subagent, no score.py) re-derived HB_HOUSTON/07-20/tft-v2: pinball
        0.976/2.691/0.794 + coverage 3/3 — EXACT match to maker. ✔ done
- [ ] 4 — Tail focus: calm vs top-decile |spread|; reliability bins where events>=5.
- [ ] 5 — Capture rhythm addition: daily /latest fetch into archive (their published-at + our capture UTC); jobs.jsonl+watchdog; DRY_RUN.
- [ ] 6 — DRAFT NOTE.md (method, independence, sign proof, tables w/ n's, tail finding, limitations). DRAFT, not for publication.

## Append-only log
- init (2026-08-02) — New loop from Mike's spec. GOAL/PROGRESS written. Recon: OUR price stores present
  (locational/, dam_decade/, price_store.py) for constraint 1. NO Kardashev API access found anywhere.
  Task 1 BLOCKED pending Mike providing (a) API base URL + auth, or (b) a CSV export of /forecast/spread/
  history + /latest schema. Nothing to fetch/freeze until then; no downstream design until T1's snapshot
  exists (constraint: report what we actually have before designing).
