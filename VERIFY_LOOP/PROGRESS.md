# Progress — MAP ANIMATION PASS

Max 14 iterations. Supervised. ONE task/commit. Fresh-eyes subagent per task. Re-read GOAL every iter.
Static-transmission gate + standing gate run EVERY task.

## Tasks
- [done] 1 — arc particles measured-only; 2px/alpha78(~30%); ARC width=flow_mw, particle speed=util,
  color=shadowTier(shadow_price) [green<$50/yellow$50-250/orange$250-1000/red≥$1000, $/MWh in comments].
  VERIFIED (fresh-eyes subagent GREEN): code (shadowTier tiers, particle 2px/78α, speed=util, width=
  flow_mw not util, measuredFlowArcs filters reported_constraint_flow, txlines static no time-dep) +
  data spot-check (ESCONDID↔GANSO flow117.6/util1.0/shadow26.74 -> GREEN) + images (arc green, motion
  localized to arc diagonal). Direct proof: __stepFlow -> all 10 particles moved along arc. Gates:
  standing=0px, transmission pure-gap=0px (step-diff=1741px = AA edges tracing STATIC line geometry,
  not motion). Screenshots: t1_particles_{a,diff}, txgate2. commit PENDING.
- [done] 2 — constraint entrance sequence for NEWLY-binding measured constraints. idSet diffs current
  vs previous frame's reported_constraint_flow ids -> startEntrance(newIds). entranceF=easeOutCubic
  (1 for existing arcs). constraint-live: width=flowWidth*entranceF (eases in), color alpha*=entranceF
  (fade in). constraint-label TextLayer = $shadow_price, alpha gated entranceF>0.7 (appears LAST). Only
  touches constraint-live/constraint-label (measured); txlines untouched. VERIFIED (fresh-eyes GREEN):
  code + 4-point probe re-derived (entProg 0.1/0.4/0.72/1.0 -> width 1.76/5.10/6.36/6.50, alpha
  41/118/147/150, labelAlpha 0/67/221/238) + /api/intraday spot-check (ESCOND_GANSO1_1 flow116.4/
  shadow45.59 -> green, label $46) + images (ent_0 faint-thin-nolabel, ent_3 full-bright-$46). Gates:
  standing=0px, transmission static (code: entrance never touches txlines). commit PENDING.
- [done] 3 — transmission de-emphasis. kvBase alphas 500=118/345=100/230=70/138=45/69=20 (~21% below
  prior 150 max; 69kV near-invisible). kvMinZoom roads-like reveal (345/500 @0, 230@5.6, 138@6.4,
  69@7.4), kvColor fades tier in over 1 zoom level; rebuild on zoomend via _mapZoom. ZERO animation
  (getLineColor deps only kv+_mapZoom-discrete; updateTriggers=round(_mapZoom*10)). VERIFIED (fresh-eyes
  GREEN): code + tier data re-derived (z4.8: only 345/500; z8.2: 69→16/138→45/230→70/345→100/500→118) +
  before/after (t4_txlines bright -> t3_metro recessive, anchors dominate) + no-anim gate. commit PENDING.
- [done] 4 — battery breathing (pure decoration). _breatheS=1+0.09sin (±9% UNIFORM scale -> relative
  MW preserved), _breatheA=0.82..1.0 opacity pulse. Disc radius*=bs + alpha pulse; column alpha pulse
  ONLY (getElevation=MW NOT pulsed). breatheTick RAF runs only when batteries.on. __stepBreathe hook.
  VERIFIED (fresh-eyes GREEN): code (uniform, elevation unpulsed, gated on batteries.on, no bleed to
  txlines) + uniformity proof (batt0 & batt1 both scale 1.055 identically; alpha 191->202) + diff
  (ring outlines at battery markers only, no other motion) + standing gate 0px. commit PENDING.
- [done] 5 — city anchors. Added Permian (5th anchor @[-102.08,31.9]); constant soft glow (steady
  box-shadow + ::before radial halo, NOT animated; anchorPulse is 1-shot self-removing load flourish).
  suppressCityLabels(): additive filter ['all',existing,['!',in name/name_en of Dallas/Houston/Austin/
  San Antonio/Midland/Odessa]] on the 3 settlement-label layers, guarded (map.__lblSuppressed), on
  style.load. VERIFIED (fresh-eyes GREEN): code + measured (5 anchors, lblSuppressed true, filter has
  exclusion, queryRenderedFeatures at all 5 pts -> none of the 6 names render) + image (5 glowing pills,
  no competing default labels, caveats intact). commit PENDING.
- [done] 6 — camera easing. Removed the last jumpTo (init pitch intro -> constructor pitch-8 +
  easeTo settle). Hub click in pop() -> map.easeTo({center:hub,zoom:max(z,6.8),duration:1200,
  essential:true}). GREP GATE: zero jumpTo/setCenter/setZoom METHOD calls (2 "jumpTo" hits are in
  comments). VERIFIED (fresh-eyes GREEN): code + call-spy (hub click -> easeTo dur1200, jumpOrSet
  false, camera 4.8/-99.1 -> 6.8/-95.37 Houston). Mid-flight screenshot = headless caveat (mapbox
  easeTo completes <80ms headless; animates in real browser). commit PENDING.
- [done] 7 — layer fade transitions. Converted per-frame *0.2 factor -> TIME-based FADE_MS=300
  easeInOutQuad per layer (frame-rate independent); startFade records _fadeFrom/_fadeT0 per toggled
  layer; buildLayers clones opacity=_op[k] so intermediate opacity renders. __setLayerOp freeze hook.
  VERIFIED (fresh-eyes GREEN): code (300ms time-based, easeInOut, records start, renderKeys keeps
  fading-out layer alive) + freeze proof (set county 0.4 -> deck props.opacity 0.4; battery 0.25) +
  mid-fade screenshot (county 30% visibly faint). Headless real-time-capture caveat noted. commit PENDING.
- [todo] 8 — sidebar "Right now" numbers roll/fade on change.
- [todo] 9 — wind arrows per-county from Open-Meteo cache, zoom-gated, static/slow.
- [todo] 10 — rest-state audit (calm+alive, <=10% animated, gates pass).
- [todo] DEPLOY — fresh-clone test, push, Fly redeploy.

## Log
- init — GOAL+PROGRESS written. Env: conda volt, ERCOT_LIVE=0. CDP driver at scratchpad/cdp.py.
  Context from prior loops: particles already exist (flow-particles ScatterplotLayer on measured
  snapshot arcs; measuredFlowArcs filters type=reported_constraint_flow). Transmission=REG.txlines
  (HIFLD, static, lazy). Batteries=ColumnLayer/disc. Anchors=4 metro pills. Briefing="Right now".
  Task 1 = refine existing particles to the ~2px/~30% + width/speed/color mapping spec.
