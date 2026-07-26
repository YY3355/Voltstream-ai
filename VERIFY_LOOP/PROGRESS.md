# Progress — Decision-Grade Charts (Bolt optimizer first, then app-wide)

Supervised. Max 10 iterations. ONE task/commit. Honesty contract (GOAL.md) in every commit.
Visual = headless screenshot working-check + FLAG for Mike's real-browser sign-off. Deploy only after
the Docker-image local gate + explicit go. Never commit red.

## Checklist — Bolt optimizer chart
- [~] 1 — Axes + units DONE (dispatchSVG): left Power(kW) signed 5 ticks + rotated title, right Stored
        energy(kWh) 5 ticks + title, both full-height & aligned (power 0 at centre = SoC midpoint), killed
        the clipped 0kW/{cap}kWh fragments. Verified: headless screenshot (clean left axis) + DOM (both
        titles + tick sets present). commit <pending>. NEEDS Mike's real-browser sign-off (visual).
        (Bars keep charge-up/discharge-down for now — T2 flips to discharge-up per convention.)
- [ ] 2 — Legend + sign convention (all series incl. blue charge).
- [ ] 3 — Price series (LMP the optimizer consumed) + per-interval tooltip from solution arrays.
- [ ] 4 — Stepped SoC (step-after) + capacity line + REAL reserve-violation flag if it crosses.
- [ ] 5 — Annotation cleanup (labels to right margin; reserve red only when threatened/breached).
- [ ] 6 — Run header + real solver status + collapsible assumptions block from solve config.
- [ ] 7 — KPI strip + insight banner (numbers from solution; capture-rate = rev ÷ PF-ceiling).
- [ ] 8 — Time axis + grid (4h ticks, gridlines, tighten margin).
## Checklist — app-wide
- [ ] 9 — Typography split (sans for text, mono for numbers/times/prices/status); per-tab screenshot.
- [ ] 10 — Axis/legend audit of every other chart (fix only).

## Append-only log
- init (2026-07-26) — New loop from GRAPH_POLISH_RECIPE.md (dropped in by Mike). Prior loop
  (structuring desk) DONE + deployed live. Wrote GOAL. NEW gates: Docker-image pre-deploy + Mike's
  real-browser sign-off on visuals. Next: explore the current Bolt chart (panel + endpoint + solution
  arrays) before task 1.
