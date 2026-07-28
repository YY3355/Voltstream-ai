# Progress — Bolt chart redesign (operational display)

Supervised. Max 12 iterations. ONE task/commit. Screenshots every iter. Push+redeploy when green.
Price overlay = the payload's solved-on series labeled "price input" (NOT a forecast). Never clip.

## Checklist
- [~] 1 — Axes DONE (kW left/kWh right + ticks + subtle grid already present) + STATED bar interval on chart "bars: 15-min intervals · 24h horizon", computed from dp.dt_hours (verified 96×0.25h=15min from payload, not assumed). Screenshot ok; label slightly near top grid -> reposition in T3. commit <pending>.
- [x] 2 — Price-input overlay DONE: series label now "price input ($/MWh) — plan solved on this" + "actual settled (ref)"; legend + tooltip carry P50 provenance. Charge bars sit in the low-price valley, discharge on the peak (visible). Screenshot ok. commit <pending>.
- [ ] 3 — Hierarchy: thick bars, SoC hero, muted price, UNMISSABLE floor (tag + red shaded zone).
- [ ] 4 — Operational: hover crosshair tooltip (kW/SoC/price) + "now" marker + on-chart header strip.
- [ ] 5 — Auto-callouts on the 2-3 largest charge/discharge runs (cap 3).

## Append-only log
- init (2026-07-28) — New loop from Mike's spec. Prior loop (graph-polish) already gave the Bolt chart
  two panels + axes + tooltip + KPI strip; this loop redesigns to a cleaner operational display per T1-T5.
  Next: verify dt/interval from /api/state payload, then T1.
