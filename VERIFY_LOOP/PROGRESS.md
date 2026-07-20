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
- [todo] 2 — constraint entrance sequence (fade->particles->width ease->label+shadow) from replay.
- [todo] 3 — transmission de-emphasis (-25% opacity, 345 bright->69 faint, zoom-tiered, ZERO anim).
- [todo] 4 — battery breathing (soft slow pulse, confined to battery markers).
- [todo] 5 — city anchors glow+label (Dallas/Houston/Austin/San Antonio/Permian), suppress default labels at 5.
- [todo] 6 — camera easing everywhere (no jumpTo in handlers).
- [todo] 7 — layer fade transitions ~300ms on toggle.
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
