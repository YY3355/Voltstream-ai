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
- [BLOCKED] 4 — battery breathing. REVERTED (commit d463529, reverts 0aebc7e). REASON: verified via
  clock-step (__stepBreathe) in headless; broken in real browser — RAF/live-playback gap. The headless
  RAF throttle meant breatheTick (which calls refreshLayers() EVERY frame, rebuilding all deck layers)
  never actually ran, so the clock-step "proof" hid that it janks/misbehaves under untouched RAF.
  Battery markers restored to EXACT pre-loop rendering: battery-layer code byte-identical to f480a19,
  getRadius=tierR (no *bs), radiusMax 14, static fill [64,150,96,205], __stepBreathe undefined,
  batteries-on framepair = 0 moved px. DO NOT re-mark done without a real-browser RAF check (see GOAL).
- [BLOCKED] 5 — city anchors. REVERTED (commit 7b18596, reverts 4e5c289). REASON: verified via headless
  (clock-step era) — broken in real browser (RAF/live-playback gap; anchors read as giant headers /
  label handling misbehaves). Also the original "suppression verified" was a FALSE PASS: headless
  swiftshader renders NO mapbox settlement labels at any zoom, so "none of the 5 render" was trivially
  true regardless of the filter. City labels restored to EXACT pre-loop: anchor list + .metro-anchor CSS
  byte-identical to f480a19, suppressCityLabels removed, settlement filters carry NO name_en exclusion,
  __lblSuppressed undefined, back to 4 anchors (Permian removed). DO NOT re-mark done without a
  real-browser RAF check (see GOAL).
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
- [done] 8 — briefing numbers roll/fade on change. Refactored renderBriefing -> briefingRows(pure)
  + paintBriefing(in-place via data-k) + __refreshBriefing. Value change -> .bv gets .rolling
  (numRoll .42s fade+slide), removed on animationend; UNCHANGED values not animated (innerHTML!==v
  guard) = no instant swap, no needless anim. Corridor "N now" = replay frame count when replaying
  (idSet -> __refreshBriefing(true)) else live n_binding. VERIFIED (fresh-eyes GREEN): code + driven
  (2->7 rolled, changed=1, class removed after, noRollOnSame true, keyframe present) + honesty/read-
  only preserved, transmission untouched. commit PENDING.
- [done] 9 — per-county wind arrows. Cache lacked wind DIRECTION, so fetched wind_direction_10m+
  wind_speed_10m CLIENT-SIDE from Open-Meteo on toggle (centroids from cwFC; same free dataset; NO
  backend work — honors scope). Static TextLayer '↑', getAngle=-(deg+180) (flow bearing from real
  dir), size~speed, zoom-gated (WIND_ZOOM 6.3), off by default, honest caveat. VERIFIED (fresh-eyes
  GREEN): code (no clock dep, no fabricated fallback) + spot-check 3 counties (Midland185/Dallas175/
  Harris189, getAngle==-(deg+180)) + live re-fetch == stored deg (real, not fabricated) + zoom-gate
  (0@z5, 254@z8) + STATIC gate (254 arrows, 0 moved px) + image. commit PENDING.
- [done] 10 — rest-state audit (verification-only). Rest frame-pair = 0 moved px (0% animated, all
  motion gated behind toggles/one-shot load). Honesty intact: banner caveat, briefing LIVE·READ-ONLY,
  9 scope caveats + 9 per-layer ⓘ (incl. wind), legend, EIA-860M/Open-Meteo/Census meta. Final
  static-transmission gate: 21px/0.001% (AA jitter on fixed geometry, no anim code). Fresh-eyes COLD
  read: "calm and controlled, not busy" — GREEN. No red flags (no price heatmap/invented data/predicted
  spike/transmission flow). commit PENDING.
- [done] DEPLOY — T1-T3 + T6-T10 shipped (8982019); after the T4/T5 revert, re-deployed the reverts
  (d6f717e). Fresh-clone test passed (build+serve; T4-conflict area clean). Prod healthy: root/state 200.

## Log
- init — GOAL+PROGRESS written. Env: conda volt, ERCOT_LIVE=0. CDP driver at scratchpad/cdp.py.
  Context from prior loops: particles already exist (flow-particles ScatterplotLayer on measured
  snapshot arcs; measuredFlowArcs filters type=reported_constraint_flow). Transmission=REG.txlines
  (HIFLD, static, lazy). Batteries=ColumnLayer/disc. Anchors=4 metro pills. Briefing="Right now".
  Task 1 = refine existing particles to the ~2px/~30% + width/speed/color mapping spec.

## RECOVERY (2026-07-20) — T4/T5 reverted, verification failure acknowledged
- User flagged T4 (battery breathing) + T5 (city anchors) broke in a REAL browser though they passed
  my headless clock-step checks (RAF/live-playback gap). Root cause: headless throttles RAF, so the
  continuous-RAF features (breatheTick rebuilding all layers every frame; anchor/label behavior) never
  actually ran live — the clock-step hooks proved the math, not the liveliness.
- Reverted (revert, not reset — history honest): 7b18596 reverts T5 (4e5c289), d463529 reverts T4
  (0aebc7e). Each = one commit. T6-T10 preserved (resolved the T9-adjacency conflict by keeping wind).
- Verified restore == EXACT pre-loop (f480a19): battery-layer code + anchor list + .metro-anchor CSS
  byte-IDENTICAL; suppressCityLabels gone; settlement filters no exclusion; __stepBreathe/__lblSuppressed
  undefined; batteries-on framepair 0 moved px; radius 14 / static fill; 4 anchors (no Permian).
- GOAL.md: added a MANDATORY standing requirement — real-browser untouched-RAF confirmation now required
  for any liveliness claim; clock-step alone no longer counts as green.

## CLOSEOUT (2026-07-20) — user chose to leave T4/T5 BLOCKED, close the loop.
- Automated REAL-BROWSER (untouched-RAF) verification proved unreliable: headful-CDP DevTools ws drops
  on this heavy mapbox+deck page across 4 approaches (single long eval, heartbeat, short-eval poll,
  Page.startScreencast) -> connection-lost / socket-closed / timeout. Per the standing requirement I
  cannot mark a liveliness task green without it, so T4/T5 were NOT re-attempted.
- FINAL: 8/10 tasks done + deployed (T1 particles, T2 entrance, T3 tx de-emphasis, T6 camera easing,
  T7 fades, T8 briefing rolls, T9 wind arrows, T10 rest audit). T4 battery breathing + T5 city anchors
  = BLOCKED (reverted, prod clean/calm). Standing requirement recorded in GOAL.md for any future re-attempt.
