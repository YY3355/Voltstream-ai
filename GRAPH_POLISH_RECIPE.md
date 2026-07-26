# Loop: Decision-Grade Charts (Bolt first, then app-wide pass)

Supervised verify-loop, max 10 iterations, ONE task = ONE commit.
Usual env recipe. Visual tasks: headless screenshot per commit is the working
check; FINAL sign-off on anything visual is Mike's real-browser eyeball
(banked T4/T5 lesson — headless has lied before). Pre-deploy gate is the
NEW rule: build + run the Docker image locally, curl endpoints against the
container, THEN hold for explicit go before `fly deploy`.

## Honesty contract for this loop
- Every number rendered (tooltips, KPIs, insight banner) comes from the
  actual solver solution arrays or archived prices. Nothing hand-written.
- NEVER visually clip/clamp data to avoid an apparent constraint crossing.
  If the solution violates reserve, render it AND flag it:
  "Reserve violation: X kWh, N intervals." If the crossing was interpolation
  artifact, the stepped line (task 4) fixes it truthfully.
- "Gross vs net revenue" distinction appears ONLY if degradation cost is
  actually a term in the MILP objective. If it isn't, show "Gross energy
  revenue" alone and say so in the assumptions block. Do not invent a
  degradation number to look sophisticated.
- Optimizer status = the real HiGHS/cvxpy status string mapped to plain
  language ("Optimal solution found" / "Infeasible" / "Time limit"), never
  a hardcoded "Optimal".
- Insight banner text is COMPUTED from the solution (detected charge/
  discharge windows + price context), not canned copy.
- Price series shown is the actual series the optimizer consumed (DA or RT,
  say which), same as-of; no resampled/smoothed stand-in.

## Tasks — Bolt optimizer chart (priority order from the critique)
1. **Axes + units.** Left axis: Power, kW (dispatch bars). Right axis:
   Stored energy, kWh (SoC). 3–5 numeric ticks each, axis titles rendered.
   Kill the clipped left-edge label fragments. Screenshot.
2. **Legend + sign convention.** Discharge = positive/up (amber), charge =
   negative/down (blue), SoC = green, reserve floor = dashed red. Explicit
   legend entries for ALL series incl. blue. Legend adjacent to plot.
   Screenshot.
3. **Price series.** Add the LMP line the optimizer actually consumed —
   either overlaid third axis (only if visually clean) or a synchronized
   panel above the dispatch bars (preferred, per critique's final
   structure). Tooltip per interval: time, LMP, action ±kW, SoC before/
   after, interval revenue = dispatch×price×Δt from the solution. All from
   solution arrays. Screenshot.
4. **Stepped SoC line.** Step-after rendering to match discrete intervals;
   add subtle 25 kWh capacity line. If stepped SoC still crosses reserve,
   that's a REAL violation → render the violation flag per contract.
   Screenshot.
5. **Annotation cleanup.** Capacity + reserve labels move to right-axis
   margin, small + muted; reserve turns red/prominent only when threatened
   (within 10%) or breached. Screenshot.
6. **Run header + status.** Replace "OPTIMIZER / CALLED" with:
   "Day-ahead dispatch optimization · <date> · <hub> · <kWh>/<kW> battery ·
   Last optimized <ts> · <real solver status>". Assumptions block
   (collapsible): round-trip eff, max power, reserve, starting SoC, market/
   price source, horizon — values read from the actual solve config.
   Screenshot.
7. **KPI strip + insight banner.** KPI row above chart: Net (or Gross —
   per contract) revenue, capture rate, equivalent cycles, final SoC,
   constraint violations. Define capture rate in a tooltip: revenue ÷
   perfect-foresight revenue, same horizon (this is the existing PF-ceiling
   concept — reuse it, cite it). Insight banner computed from solution
   windows. Screenshot.
8. **Time axis + grid.** Ticks every 4h, subtle vertical gridlines,
   tighten bottom margin; sub-hourly detail via hover only. Screenshot.

## Tasks — app-wide pass (cheaper, mechanical)
9. **Typography split.** Sans-serif for nav/titles/labels/explanatory text;
   monospace retained for numbers, times, prices, statuses. One CSS pass,
   verify no layout breaks per tab (screenshot each tab).
10. **Axis/legend audit of every other chart** (decade playback, hedge
    panel, vol cone, DART monitor, desk table sparklines if any): every
    chart gets axis titles + units + ≥3 ticks + complete legend. Fix only —
    no redesigns, no new data. Screenshot each.

## Out of scope (do not drift)
New data sources, new endpoints, map/deck.gl anything (T4/T5 stay blocked),
animation, redesigning panels beyond the listed fixes, any deploy without
the Docker-image gate + explicit go.
