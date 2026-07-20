# GOAL — MAP ANIMATION PASS (make the map feel alive; ONLY measured data or pure decoration)

Supervised. Max 14 iterations. ONE task/iteration, ONE commit/task, pause+report after each.
Never commit red. Same check red 3x = mark blocked + stop. Re-read this + PROGRESS every iteration.

## HARD CONSTRAINTS (violating any = RED even if it renders)
1. Particles/flow animation ONLY on MEASURED constraint arcs (NP6-86-CD, both-ends crosswalk-matched).
   NEVER on HIFLD transmission lines — no particles, no directional motion, no "energy flowing" on
   unmeasured geometry. Transmission = context = STATIC.
2. Every animated data channel maps to a measured field: arc width = flow MW; arc speed = utilization
   (flow/limit); arc color = shadow-price tier (thresholds stated in code comments w/ units). Wind
   arrows = Open-Meteo direction/speed at county centroids.
3. Pure decoration ONLY where it can't be read as data: battery breathing, city glow, camera easing,
   layer fades, sidebar number transitions. NO drifting clouds / moving rain (reads as radar we lack).
4. Still banned: price heatmaps from 4 hubs, invented coords, estimated transfer arcs, "predicted
   spike in N min" text. NEVER delete honesty labels / caveats / match-rate displays.
5. Motion budget: at rest <=10% of viewport animating. Busy rest-state screenshot = RED.

## ENV
conda run -n volt; ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean; kill stale :8020; warm /api/dart + risk;
headless Chrome via CDP (scratchpad/cdp.py); verify vs committed 7/16 intraday replay snapshot
(deterministic — no live API in the loop).

## VERIFICATION (maker != checker — spawn fresh-eyes subagent per task)
a) Load Map tab in headless Chrome, wait ~5s for layers.
b) FRAME PAIR (2 screenshots ~2s apart, same camera). Pixel-diff masked to the layer under test:
   motion INSIDE intended layer, NEVER on HIFLD transmission (static-transmission gate EVERY task).
c) Standing gate: all animated layers OFF -> map perfectly still except Mapbox base.
d) Arc data spot-check: read flow/limit/shadow from fixture JSON for one arc; confirm rendered
   width/speed-class/color-tier match the mapping in code. Pretty arc + wrong number = RED.
e) Log screenshots + diff summary in PROGRESS.md.

## TASKS (in order)
1. Arc particles on measured constraint arcs ONLY — ~2px, ~30% opacity, understated. width=MW,
   speed=utilization, color=shadow-price tier (green/yellow/orange/red). Verify b+d+static gate.
2. Constraint entrance sequence for a newly-binding constraint from replay: fade in -> particles
   start -> width eases to MW -> label+shadow price appear. Verify: drive replay, 4 timed shots.
3. Transmission de-emphasis: opacity -25%, 345kV brightest -> 69kV near-invisible, zoom-tiered like
   roads, ZERO animation. Verify: before/after; arcs+cities dominate eye path, not transmission.
4. Battery breathing: soft slow scale/opacity pulse on battery markers. Verify: frame-pair motion
   confined to battery markers.
5. City anchors: custom glow+label for Dallas/Houston/Austin/San Antonio/Permian; suppress default
   Mapbox labels at those 5 only. Constant soft glow. Verify: screenshot.
6. Camera easing: all interactions easeTo()/flyTo(); grep jumpTo/instant setCenter in handlers = RED;
   CDP-click a hub, screenshot mid-flight.
7. Layer fade transitions ~300ms on toggle. Verify: toggle via CDP, capture mid-transition partial opacity.
8. Sidebar "Right now" numbers roll/fade on change (no instant swaps). Verify: mutate via replay tick, mid-transition shot.
9. Wind arrows: subtle per-county arrows from existing Open-Meteo cache, zoom-gated, static/very slow.
   Verify: spot-check 3 counties' arrow bearings vs cached values.
10. Rest-state audit: full-map at rest; fresh-eyes subagent describes cold -> "calm, alive" not "busy";
    <=10% animated; caveats/tooltips present; static-transmission gate final pass.

## DONE / SCOPE
No new datasets, no AI, no backend work. All 10 green -> fresh-clone test -> push + Fly redeploy.
Final report: done+verified list w/ commit hashes, anything blocked and why.
