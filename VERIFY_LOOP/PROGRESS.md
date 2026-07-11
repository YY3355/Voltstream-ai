# Progress — hedge_study.py wiring (hedging layer on the Decade Study)

Max 12 iterations. Supervised.

## Tasks
- [done] T1 — decade_run.py persists per-day revenue table + per-year realized_avg + ACTUAL
  discharge_mwh_per_day. Verified: decade fixture PASSES; decade_result.json (4.4KB) has
  discharge=4.527 + realized_avg all years; /api/decade -> 200. commit 3b9dda5.
- [done] T2 — hedge_run.py runs sweep on real 8y. Verified: both fixtures PASS; Uri $183,212
  -> $20,765 (capped); MIN-VARIANCE RATIO = 0.5 INTERIOR (std 61k->46k->54k); F0=$52.42.
  hedge_result.json 2.5KB committed + .dockerignore un-exclude. commit 91c3749.
- [done] T3 — /api/hedge endpoint. Verified 200, all keys, min_variance 0.5/interior, Uri
  sanity intact. commit 46752b4.
- [done] T4 — Quant panel #6. Verified: /api/hedge 200; headless /#quant DOM shows both SVGs
  (curve w/ interior-min mark + merchant-vs-hedged bars) + takeaway + honest labels; lazy-load
  clean (empty on /). Screenshot confirms layout. commit 51a2765. PUSHED 42ce19d..51a2765.

ALL GREEN — 4/12 iterations. Pushed.

## Log
- init — goal pinned, decade_study dispatch/backtest read; discharge needs exposing.
