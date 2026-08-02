# Progress — Kardashev RT-DA spread forecast audit

Supervised. Max 8 iterations. ONE task = ONE commit. Pause + report each. Never commit red; 3x red = blocked.
No LLM in scoring. No harness/signal.py/deploy/UI. Independence = OUR stores are ground truth, never their API.

## Checklist
- [~] 1 — Fetch + freeze their /forecast/spread/history -> snapshot_<date>/; document schema; report span/n/quantiles.
        BLOCKED: no Kardashev API base-URL/creds/CSV present anywhere (repo/env/.zshenv). Need Mike to provide access.
- [ ] 2 — Sign + alignment gate: empirical mapping on 3 days + tz/hour-convention pin. ⏸ STOP, show evidence. (blocked by T1)
- [ ] 3 — Join + score: pinball per quantile, coverage vs 80% (P10-P90), our baselines on identical coords. Checker re-derives 1.
- [ ] 4 — Tail focus: calm vs top-decile |spread|; reliability bins where events>=5.
- [ ] 5 — Capture rhythm addition: daily /latest fetch into archive (their published-at + our capture UTC); jobs.jsonl+watchdog; DRY_RUN.
- [ ] 6 — DRAFT NOTE.md (method, independence, sign proof, tables w/ n's, tail finding, limitations). DRAFT, not for publication.

## Append-only log
- init (2026-08-02) — New loop from Mike's spec. GOAL/PROGRESS written. Recon: OUR price stores present
  (locational/, dam_decade/, price_store.py) for constraint 1. NO Kardashev API access found anywhere.
  Task 1 BLOCKED pending Mike providing (a) API base URL + auth, or (b) a CSV export of /forecast/spread/
  history + /latest schema. Nothing to fetch/freeze until then; no downstream design until T1's snapshot
  exists (constraint: report what we actually have before designing).
