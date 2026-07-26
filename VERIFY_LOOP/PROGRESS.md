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
- [~] 2 — Sign flip DONE (render-layer only): discharge +/up amber, charge -/down blue; legend updated
        (all 4 series incl. blue charge + dashed reserve floor); footer sign note. Arrays untouched.
        Screenshot confirms. commit <pending>. Real-browser sign-off pending.
- [~] 3 — Price panel + tooltip DONE. Synchronized LMP($/MWh) panel ABOVE dispatch: P50 (the series Bolt
        optimized against, cyan) + actual settled (faint). Per-interval hover tooltip: time, P50/actual,
        action ±kW (net from raw arrays), SoC before→after (initial→soc[i]), interval rev = net×actual×dt.
        Surfaced status/initial_soc/max_power/eff/dt in the dispatch dict (existing solve data, not a new
        source). VERIFIED: tooltip interval revenues sum to \$0.634 ≈ realized KPI \$0.64. commit <pending>.
- [~] 4 — Stepped SoC (step-after staircase) + subtle 25 kWh capacity line + conditional reserve-
        violation flag (red banner + red dots, only when soc<reserve). STOP-CONDITION FINDING: NO real
        violation — min SoC 10.0 = reserve, 0 intervals below (MILP enforces soc>=reserve). Flag stays
        off; MILP untouched. Note: SoC is physically piecewise-LINEAR within intervals (constant power);
        step-after is the requested discreteness rendering — flagged for Mike's sign-off. commit <pending>.
- [~] 5 — Annotation cleanup DONE: capacity+reserve labels at right-axis margin, small+muted; reserve line + label turn prominent red +warn ONLY when threatened (minSoc<=reserve*1.1) or breached, else muted gray. Here threatened=true (minSoc=reserve). DOM-verified. commit <pending>.
- [~] 6 — Run header DONE: "Day-ahead dispatch optimization" + line: date·hub·25kWh/12.5kW·last optimized <computed_at>·<REAL solver status mapped to plain language "Optimal solution found">. s-dp shows status. Collapsible assumptions block (eff/power/cap/reserve/startSoC/horizon/price source/HiGHS) + "gross energy-arbitrage revenue only, no degradation in MILP". Added computed_at to state. commit <pending>.
- [~] 7 — KPI strip + insight banner DONE. KPIs above chart (all from solution arrays): GROSS revenue $0.64 (no net — no degradation in MILP, per contract), CAPTURE RATE 70% w/ tooltip (realized ÷ PF-ceiling $0.91, same 24h), EQUIV CYCLES 2.05 (dischargeE/cap), FINAL SoC 12.5, VIOLATIONS 0. Insight banner COMPUTED from charge/discharge windows+avg prices ($25 low->$40 high). Verified numbers vs arrays. commit <pending>.
- [~] 8 — Time axis DONE: ticks every 4h (00:00..24:00 from fc.hours) + subtle vertical gridlines across both panels (behind data), tightened bottom margin; sub-hourly via hover only. DOM shows all 7 ticks. commit <pending>. ALL 8 Bolt-chart tasks done — decision-grade.
## Checklist — app-wide
- [ ] 9 — Typography split (sans for text, mono for numbers/times/prices/status); per-tab screenshot.
- [ ] 10 — Axis/legend audit of every other chart (fix only).

## Run mode (Mike) — BATCH 2→10, no deploy
- Run tasks 2-8 then 9-10 straight through; each commits its own headless screenshot (working check).
- SIGN FLIP (T2): render-layer ONLY. Solution arrays keep solver-native magnitudes; discharge=+/up
  (energy to grid = earning) applied at DRAW time. Tooltips/KPIs consume RAW arrays. Footer sign note.
- T4 STOP CONDITION: if the stepped SoC reveals a REAL reserve violation in the arrays -> render + flag
  "Reserve violation: X kWh, N intervals" per contract, do NOT touch the MILP (solver = out of scope),
  REPORT the finding, keep going. Optimizer fix decided separately.
- END: NO deploy. Mike clicks every tab on :8020 (visual sign-off; headless doesn't count) -> Docker-
  image local gate (build+run container, curl) -> then explicit go.

## Append-only log
- init (2026-07-26) — New loop from GRAPH_POLISH_RECIPE.md (dropped in by Mike). Prior loop
  (structuring desk) DONE + deployed live. Wrote GOAL. NEW gates: Docker-image pre-deploy + Mike's
  real-browser sign-off on visuals. Next: explore the current Bolt chart (panel + endpoint + solution
  arrays) before task 1.
