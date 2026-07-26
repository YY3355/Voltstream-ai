# GOAL — Decision-Grade Charts (Bolt optimizer first, then app-wide pass)

Full spec: GRAPH_POLISH_RECIPE.md. Supervised verify-loop, max 10 iterations, ONE task = ONE commit.
Env: conda volt on :8020, ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean, kill stale port, warm dart+risk.

## NEW procedural rules (banked lessons)
- VISUAL check per commit = headless screenshot (the working check). FINAL sign-off on ANYTHING
  visual is Mike's REAL-BROWSER eyeball — headless has lied before (T4/T5 lesson). So: screenshot +
  commit, but flag "needs Mike's real-browser sign-off" for visual tasks; don't call visual "done".
- PRE-DEPLOY GATE (hard): before any `fly deploy`, BUILD + RUN the Docker image LOCALLY and curl the
  endpoints against the container (catches .dockerignore/COPY gaps the raw-clone test misses — last
  loop's snapshot-bug), THEN hold for Mike's explicit go. No deploy without the container gate + go.

## Honesty contract (NON-NEGOTIABLE)
- Every rendered number (tooltips, KPIs, insight banner) comes from the actual solver solution arrays
  or archived prices. Nothing hand-written / canned.
- NEVER visually clip/clamp data to hide a constraint crossing. Render it AND flag: "Reserve
  violation: X kWh, N intervals." A stepped line (T4) fixes interpolation artifacts truthfully.
- "Gross vs net revenue" ONLY if degradation cost is actually a term in the MILP objective. If not:
  "Gross energy revenue" alone + say so in the assumptions block. No invented degradation number.
- Optimizer status = the REAL HiGHS/cvxpy status string mapped to plain language, never hardcoded.
- Insight banner text COMPUTED from the solution (charge/discharge windows + price context), not canned.
- Price series shown = the actual series the optimizer consumed (DA or RT — say which), same as-of.

## Tasks — Bolt optimizer chart (priority order)
1. Axes + units: L axis Power kW (bars), R axis Stored energy kWh (SoC), 3-5 ticks + titles each; kill
   clipped left-edge label fragments. Screenshot.
2. Legend + sign convention: discharge +/up amber, charge -/down blue, SoC green, reserve floor dashed
   red; explicit legend for ALL series incl. blue; legend adjacent. Screenshot.
3. Price series: add the LMP line the optimizer consumed (synchronized panel above bars preferred).
   Per-interval tooltip: time, LMP, action ±kW, SoC before/after, interval revenue = dispatch×price×Δt
   (all from solution arrays). Screenshot.
4. Stepped SoC (step-after) to match discrete intervals; subtle 25 kWh capacity line; if stepped SoC
   still crosses reserve, render the REAL violation flag. Screenshot.
5. Annotation cleanup: capacity+reserve labels to right-axis margin, small+muted; reserve red/prominent
   only when threatened (within 10%) or breached. Screenshot.
6. Run header + status: "Day-ahead dispatch optimization · <date> · <hub> · <kWh>/<kW> battery · Last
   optimized <ts> · <real solver status>". Collapsible assumptions block (eff, max power, reserve,
   start SoC, market/price source, horizon) from the actual solve config. Screenshot.
7. KPI strip + insight banner: KPI row (Net|Gross revenue per contract, capture rate, equiv cycles,
   final SoC, violations). capture rate tooltip = revenue ÷ perfect-foresight revenue same horizon
   (reuse the existing PF-ceiling concept, cite it). Insight banner computed from solution. Screenshot.
8. Time axis + grid: ticks every 4h, subtle vertical gridlines, tighten bottom margin; sub-hourly via
   hover only. Screenshot.

## Tasks — app-wide pass (mechanical)
9. Typography split: sans-serif for nav/titles/labels/explanatory text; monospace ONLY for numbers,
   times, prices, statuses. One CSS pass; verify no layout breaks per tab (screenshot each tab).
10. Axis/legend audit of every other chart (decade playback, hedge, vol cone, DART monitor, desk-table
    sparklines): axis titles + units + >=3 ticks + complete legend. FIX ONLY, no redesigns/new data.
    Screenshot each.

## Verify discipline
Fresh-eyes subagent per task where it adds signal (data-honesty, numbers-from-solution). Screenshot
each visual task (headless working check). Never commit red. Same check red 3x = blocked.

## OUT OF SCOPE (do not drift)
New data sources, new endpoints, map/deck.gl (T4/T5 stay blocked), animation, panel redesigns beyond
the listed fixes, ANY deploy without the Docker-image gate + explicit go.
