# GOAL — MAP DESIGN ELEVATION (engineering UI → product design)

Pure visual/UX + ONE context-data add (HIFLD transmission lines). All in dashboard_live.html's
Map card + initMap (+ small app.py endpoint for the data add). Do NOT touch other tabs/engines.
Judged by EYES: screenshot at state zoom + metro zoom every iteration.

## Current state (pre-loop, from code read)
- Map: mapbox-gl v3.9.0 + deck.gl 9.0.35. dark-v11 style, flat (pitch 0), TX_VIEW center[-99.7,31.25]
  zoom 5.55. Overlay=MapboxOverlay(interleaved:false). Z_ORDER=['county','hubs','batteries','plants',
  'cities','locational','constraints'] + always-on county-outline at bottom. Fade animation (_op/
  animateFade). Flow particles: ScatterplotLayer dots along MEASURED snapshot arcs (already ●-style).
- Batteries: ScatterplotLayer (flat circles, radius ~ sqrt MW). County: fill GeoJsonLayer + outline.
- Sidebar (.map-side): #layer-insight (per-active-layer stat), #county-panel (battery MW bar — DO NOT
  TOUCH data), #scope-details. Banner #map-wxbanner (wind belt). #alert-strip (loadAlerts).
- Design tokens: --mono IBM Plex Mono, --sans IBM Plex Sans; colors amber/green/red/blue/violet.
- Endpoints available for briefing: /api/rt (RT prices), /api/constraintarcs (90d + live), /api/map
  (DART), /api/countyweather (wind_signal + hottest), alerts via loadAlerts.

## Tasks (commit each; screenshots each)
### PHASE A — depth & atmosphere
- **T1 CAMERA + ATMOSPHERE**: default pitch ~40-45°; Mapbox fog + sky (subtle, dark); optional gentle
  terrain (mapbox-dem, low exaggeration); CSS soft vignette over the canvas. Reads as 3 planes.
- **T2 3D BATTERIES**: batteries → deck.gl ColumnLayer, height = real MW (honest extrusion), muted
  green, small footprint. Flat discs at low zoom, columns as you zoom in (zoom-switch). Still pickable.
- **T3 ZOOM-TIERED REVEAL**: at state zoom show ONLY anchors — Houston/Dallas/Austin/San Antonio
  designed labels (rounded, subtle glow, NOT raw mapbox labels), 5 largest batteries, top congestion
  corridor. Rest fades in with zoom (Google-Maps principle). Radii on the 4/5/7/10/14 scale.
### PHASE B — hierarchy & motion
- **T4 TRANSMISSION CONTEXT (data add)**: fetch HIFLD transmission lines Texas subset → cache
  data_archive/geo/tx_lines.geojson; app.py /api/txlines serves it. Render voltage-tiered: 69kV thin
  gray → 138 blue → 230 teal → 345 cyan → 500 white, subtle opacity. Label verbatim: "transmission
  context (HIFLD geometry) — constraint status shown only by the measured SCED arcs." Off by default,
  one toggle.
- **T5 PALETTE DISCIPLINE**: 4 semantic colors — blue grid infra, green batteries, red congestion
  ONLY, amber weather-heat — everything else muted/gray. Counties: gradient opacity + soft hover glow
  (not flat fill).
- **T6 ARC PARTICLES**: moving dots along MEASURED arcs (●──►), density by utilization. Measured arcs
  ONLY (verify rule holds). (Largely present — refine to dot style + density, confirm measured-only.)
- **T7 SIDEBAR AS BRIEFING**: top of sidebar = "Right now": live RT price by hub (biggest mover
  highlighted), top congestion corridor (90d + live-now), wind-belt state, hottest county, active
  alerts count. From EXISTING endpoints. NO new claims, NO "recommended dispatch" language.
- **T8 MOTION + TYPO**: layers fade, tooltips slide, anchors pulse once on load, sidebar expands
  smoothly. Typography pass: one font family, small/consistent/muted — kill the dev-dashboard look.

## Definition of done
- 3 planes read (terrain/fog → infra → intelligence); pitched camera; batteries extruded by MW.
- State zoom = calm anchors only; detail fades in with zoom; transmission tiers distinguishable.
- 4-color palette; particles = measured-arc dots only; sidebar "Right now" briefing from real data.
- Batteries pickable; anchors legible in 3s; all caveat tooltips reachable; other tabs untouched.
- Pushed when green; redeploy Fly.

## Verify (CDP + SCREENSHOTS — visual, every iteration)
- Screenshots: state zoom, metro zoom (Houston), each phase's layers on. CDP: batteries pickObject
  ok; deck layers present; measured-arc particles only (flowArcs all type=reported_constraint_flow);
  caveat tooltips in DOM; other tabs render.

## Guardrails
- Max 18 iterations. Supervised. One task = one commit. Green commits only.
- NO fabricated data: HIFLD = geometry context ONLY (constraint status stays with measured SCED arcs);
  particles measured-arcs only; no "recommended dispatch" in the briefing. Do NOT touch #county-panel
  data / /api/countyheat or other tabs. Keep every honesty caveat reachable.
