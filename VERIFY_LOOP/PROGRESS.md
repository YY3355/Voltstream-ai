# Progress — MAP DESIGN ELEVATION

Max 18 iterations. Supervised. Screenshots EVERY iteration (state zoom + metro zoom). Judged by eyes.

## Tasks
- [done] T1 — camera pitch 52° + bearing -6, zoom 4.8 framing that reveals an atmospheric horizon;
  Mapbox setFog (dark, horizon-blend .14 — verified getFog true); CSS .map-vignette overlay; T8
  pitch-in settle. Terrain DROPPED: raster-DEM needs WebGL our swiftshader harness can't render, so
  unverifiable — pitch+fog+vignette already give the depth (3 planes read: horizon→TX→markers).
  Verified: pitch 52, fog set, vignette in DOM, deck layers intact; state screenshot cinematic. commit PENDING.
- [done] T2 — batteries: ColumnLayer (extruded, getElevation∝real MW, elevationScale ~9km max,
  radius 2200m small footprint, muted green, ambient+dir LightingEffect) at zoom>=7; flat green
  pickable discs below; zoom-flip refresh only on threshold cross. Verified in-harness: overview
  discs = ScatterplotLayer fill [64,150,96] muted green, pickObject → 'batteries' (pickable);
  zoom-switch flips disc(Au)↔column(Iu). DEFERRED to real-GPU deploy (user OK'd): column lit-green
  color + column click-pick — SwiftShader can't render/pick deck extruded geometry (renders dark,
  pickObject null); standard deck.gl behavior on real GPUs. commit PENDING.
- [done] T3 — zoom-tiered reveal + anchors. Designed metro labels (Houston/Dallas/Austin/San Antonio)
  as rounded glass pills w/ glow + leading dot (NOT raw mapbox labels), created synchronously (the
  map 'load' event stalls in-harness — also fixed the T1 easeTo via style.load + setTimeout settle).
  Battery zoom-reveal: top-5 at state zoom -> more as you zoom -> all at metro (verified 5 -> 189/235).
  Radii compressed to 4/5/7/10/14 tiers (verified hubs {7,12,16}, batteries {14}). Top congestion
  corridor = persistent subtle red ArcLayer of the #1 90d-binding aggregate arc (measured; arcTip
  caveat). Verified: 4 anchors present+legible, battReveal 5/189, top-corridor layer present. commit PENDING.
- [done] T4 — HIFLD transmission CONTEXT. Fetched HIFLD Electric Power Transmission Lines (TX bbox,
  69kV+, 6965 lines) -> data_archive/geo/tx_lines.geojson (4.8MB, 3dp coords, kv only; force-added +
  .dockerignore allow). app.py /api/txlines serves it (200, count 6965, verbatim label). Dashboard:
  REG.txlines OFF by default, LAZY-fetched on first toggle (toggle enabled pre-load via lazy flag),
  voltage-tiered GeoJsonLayer (69 gray/138 blue/230 teal/345 cyan/500 white, subtle), txTip caveat,
  legend gradient. Verified: endpoint 200/6965/label; toggle enabled; lazy-load populated 6965; 6
  distinct kv tiers w/ distinct colors; metro screenshot = tiered grid web around Dallas. commit PENDING.
- [done] T5 — palette discipline. Semantic 4 kept: blue transmission / green batteries / red
  congestion (arcs + top corridor) / amber county heat. Killed the rainbow: plants techColor -> muted
  gray, cities -> muted gray (identity in tooltip). Counties: GRADIENT OPACITY by temp (74°F→α48
  faint .. 106°F→α188 opaque — cool recede so basemap reads through = depth; hot pop) + soft amber
  autoHighlight hover glow. Legend swatches updated (battery green, plant/city gray). Hubs keep
  green/red as the price hero (the DART signal) — noted exception. Verified: Presidio α55 vs Dimmit
  α148, plants/cities gray fills, autoHighlight on; state screenshot shows the heat-depth gradient. commit PENDING.
- [done] T6 — arc particles already meet spec (no ribbon existed); VERIFIED via intraday replay
  (live arcs honestly empty in dev). Drove a measured frame: flow-particles = ScatterplotLayer DOTS,
  density by utilization (util 1.0 -> 10 dots = 3+round(1·7)), and measuredFlowArcs enforces
  measured-ONLY (allMeasuredOnly true: every animated arc type=reported_constraint_flow w/ src+tgt).
  Screenshot: white dots flowing along the single measured SCED arc. Verification-only, no code change.
- [done] T7 — sidebar "Right now" briefing at the top of .map-side. 5 rows from EXISTING endpoints:
  DA−RT biggest mover + rich/cheap (hubs), top corridor stations+90d bind%+live-now (arcAgg + alerts
  n_binding), wind-belt state (cwWind), hottest county (cwFeats), alerts count+severity (/api/alerts).
  Read-only, no new claims, NO dispatch language (verified regex hasDispatchLanguage=false). Verified:
  5 rows populate w/ real values (Houston -2.28, HHGT↔OMEGA 10.9%/1 now, LIGHT 11.3, Dimmit 96.8°F,
  2 watch); screenshot shows a clean designed situation board. commit PENDING.
- [todo] T8 — motion (fades/slides/anchor pulse/section expand) + typography pass (one family, muted).
- [todo] DEPLOY — push, redeploy Fly.

## Log
- init — read map HTML section (#map-canvas, .map-side, banner, alert-strip, legend), CSS design
  tokens + map CSS, map init (mapbox dark-v11 flat pitch0, TX_VIEW zoom5.55, easeTo on load),
  LAYER_CAVEATS, Z_ORDER + county-outline. CDP driver ready (scratchpad/cdp.py: screenshot + eval,
  swiftshader). Plan: T1 first (self-contained camera/atmosphere), read per-task code as reached.
