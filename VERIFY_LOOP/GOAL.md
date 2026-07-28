# GOAL — BOLT CHART REDESIGN (panel 1, Asset Optimization): static log → operational display

Pure UI + ONE honest data overlay (the price input). Screenshots EVERY iteration (default + hover).
Supervised, max 12 iterations, ONE task = ONE commit. Push when green, redeploy. Other panels untouched.
Env: conda volt on :8020, ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean. Real-browser sign-off is Mike's;
headless screenshot is the working check. Docker-gate intent before deploy.

## Honesty (non-negotiable)
- Every rendered number from the /api/state solution arrays. Nothing hand-written.
- The price overlay is the series the plan was SOLVED ON (from the payload), labeled "price input
  ($/MWh)" — an INPUT/given, NOT presented as a forward-looking forecast. (Reality: the plan solved on
  the P50 series; label it as the input it is, and note P50 in the tooltip — do not imply it predicts.)
- Never clip/clamp. Reserve floor rendered truthfully. Bar interval STATED from the actual cadence
  (verify dt from payload — 96 intervals × 0.25h = 15-min; confirm, don't assume).

## Tasks
- T1 AXES: explicit left y-axis kW (charge/discharge bars, labeled ticks), explicit right y-axis kWh
  (SoC). Subtle gridlines. STATE the bar interval on the chart ("15-min intervals" — from the payload).
- T2 PRICE CONTEXT: price series Bolt optimized against as a thin muted line (own scale, right side or a
  slim subpanel above), labeled "price input ($/MWh)" — the payload's solved-on series, NOT a forecast.
  Charge bars sit in price valleys, discharge on peaks — the chart explains itself.
- T3 HIERARCHY: thicken bars (min 3-4px + slight gap, distinguishable when busy); SoC line the hero
  (2px bright green); price line muted; backup floor UNMISSABLE — solid red 1.5px + "backup floor 10 kWh"
  tag pinned at the line's right end + faint red shaded zone below it.
- T4 OPERATIONAL FEEL: hover crosshair showing time + all values (kW, SoC, price) in a tooltip; a "now"
  vertical marker if the plan covers the current time; ACTION NOW / CAPTURE / REV moved into a header
  strip on the chart with current-hour values highlighted; CAPTURE gets a one-line ⓘ (realized vs
  perfect-foresight ceiling).
- T5 ANNOTATIONS: auto-callouts on the 2-3 LARGEST events only (biggest discharge run, biggest charge
  run) — small labels "discharge 3.2 kWh @ $41 avg". Cap at 3, no clutter.

## Verify each
Screenshots at default + hover. Axes labeled; interval stated matches actual cadence; price line present
+ labeled as input; floor unmissable; other panels untouched. Numbers reproduce from arrays. Never red.
