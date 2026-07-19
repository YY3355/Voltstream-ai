# Progress — Map visual redesign (pure UI)

Max 15 iterations. Supervised. Verify with CDP + SCREENSHOTS each task.

## Tasks
- [done] T1 — defaults county+hubs ON only; TX frame center[-99.7,31.25] zoom5.55. Verified CDP
  (active==[county,hubs], bounds -105.8..-93.6 tight) + screenshot. commit ee5fafc.
- [done] T2 — #map-scope emptied+hidden; per-layer ⓘ tooltips + sidebar "Data & scope" details.
  Verified CDP: scope empty, all 8 caveats+extra reachable in DOM (sidebar+tips), details opens.
  commit 6ca4eff.
- [done] T3 — arcs 2-4px/alpha135(53%)/muted-cyan blend; markers compressed (county 2.56x);
  subdued palette; cyan transmission legend. Verified CDP (widths 2-4, alpha 135, ratio 2.56) +
  screenshots (calm markers, translucent blending arcs). commit 557edbc.
- [done] T4 — sidebar insight cards per active layer (county "87 counties·16,317 MW·top Brazoria
  1,252 MW", hubs rich/cheap, constraints "49 corridors·25% placed"). Verified CDP + screenshot.
  commit ef0a2fe.
- [done] T5 — layer opacity fade on/off (0.74/0.33 mid-fade, settles) + camera easeTo TX frame
  (zoom 5.55). Verified CDP; no regression (flow/intraday/quant ok). commit f48844c.
- [doing] DEPLOY — push, redeploy Fly.

## Log
- init — REG has 8 layers (no substations layer). map-scope@1754 big box over canvas. controls@
  1624. camera default {-99.3,31.2,zoom5.4}@1500. refreshLayers@1595. Plan: add caveat+op fields
  to REG; fitBounds TX; per-layer ⓘ + Data&scope collapsible; compress radii; thin/translucent
  arcs; opacity fade controller.
