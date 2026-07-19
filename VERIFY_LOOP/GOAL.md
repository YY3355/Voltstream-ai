# GOAL — MAP VISUAL REDESIGN (pure UI, no new data/engines)

Make the Map tab a calm decision-support surface with progressive reveal. All in
dashboard_live.html (Map card + initMap). Do NOT touch other tabs, endpoints, or engines.

## Current state
- REG layers (8): hubs, batteries, plants, cities, county, weather, locational, constraints.
  (No standalone "substations" layer exists — apply default-off spirit to the 8 that do.)
  Current defaults ON: hubs, batteries, cities. Camera: center {-99.3,31.2} zoom 5.4 (too wide —
  shows NM/OK/LA/Mexico). map-scope = a big absolute honest-scope box over the canvas. Controls =
  horizontal chip row (#map-controls). Right panel = #county-panel (county list). Legend =
  #map-legend, meta = #map-meta.

## Tasks (commit each)
- **T1 DEFAULT + FRAMING**: default ON = county + hubs ONLY; all others OFF. Tighten initial
  camera to frame Texas snugly (fitBounds a TX bbox, not the wide zoom-5.4). Calm default
  answers "where's the congestion value".
- **T2 SCOPE RELOCATION**: remove the large #map-scope box from the canvas. Move every caveat
  into (a) a sidebar collapsible "Data & scope" section, and (b) per-layer ⓘ tooltips next to
  each layer toggle (hover/click shows THAT layer's caveat). NOTHING deleted — every caveat
  still reachable in the DOM. Verify each layer's caveat text still exists.
- **T3 VISUAL DISCIPLINE**: arcs 2-4px, 40-60% opacity, blend on overlap (translucent, not
  opaque spaghetti). Marker radius range compressed to ~2-3x (not ~10x). Palette subdued: at
  most 1-2 active colors/layer, muted (county reds, cyan transmission, charcoal sidebar), rest
  subdued. Reduce competing labels.
- **T4 SIDEBAR AS INSIGHT**: the layer sidebar carries context — for each active layer show a
  couple of summary stats (county → "87 counties, 16,317 MW, top Brazoria 1,252 MW"; arcs →
  "49 corridors, 25% placed"; hubs → "4 hubs, N rich / M cheap"; etc.).
- **T5 SMOOTH TRANSITIONS**: layers fade/animate on/off (not pop); camera eases (easeTo/
  fitBounds duration).

## Definition of done
- Default view is calm: exactly county + hubs active; framing tight on Texas.
- All scope caveats reachable via sidebar "Data & scope" + per-layer ⓘ (verified text in DOM).
- Arcs thin (2-4px) + translucent; markers compressed (~2-3x); palette subdued.
- Active-layer summary stats in the sidebar.
- Toggling a layer fades (no hard pop); camera eases.
- Other tabs untouched. Pushed when green; redeploy Fly.

## Verify (CDP + SCREENSHOTS — this is visual, screenshots matter)
- Screenshot the default view: only 2 layers, Texas framed tightly.
- CDP: window.__activeLayers == [county,hubs] at load; map bounds within a TX-tight box; each
  layer caveat string present in DOM; arc getWidth <=4 & alpha in 40-60%; radius max/min ~2-3x;
  toggling a layer animates opacity (not instant); other tabs render.

## Guardrails
- Max 15 iterations. Supervised. One task = one commit. Green commits only. Pure UI — no data/
  engine/endpoint changes. Do not break existing layer/alert/flow/intraday behavior or the
  honesty content (relocate, never delete).
