# Progress — Map Phase 1 (geo layers + controls + fix zoom)

Max 12 iterations. Supervised.

## Prereq blocker
- EIA key 403 INVALID -> no batteries/plants cache. Cities real (28). Will seed fixture-shaped
  cache for layer-mechanics verification (NOT committed); real EIA data pending a valid key.

## Tasks
- [done] T1 — fix zoom/pan (interleaved:true + NavigationControl + window.__map). Verified via
  CDP on real /#map: wheel 5.4->5.97, setZoom->7.9, scrollZoom+dragPan on, nav buttons present,
  canvasCount 2->1 (overlay canvas gone). commit 7b1dfff.
- [done] T2 — /api/geo endpoint + geo_data.py committed. Verified both paths: empty-state (28
  cities, 0 batt/plants, assets_note) and real-counts via fixture-seeded cache (2 batt w/ full
  fields, 2 plants w/ tech, county_rollup MW-desc). commit 24bd6d3. NOTE: seeded cache is
  gitignored + .dockerignored -> Fly shows honest empty-state until a real EIA fetch runs there.
- [done] T3+T4 — layer controls + Batteries/Plants/Cities layers + click popups + honest
  labels. Verified CDP: toggle flips active set, battery pickable+popup renders correct fields,
  labels present; fresh screenshot shows 4 hubs+28 cities+2 batteries placed correctly. commit
  2e6cb82. CORRECTION: interleaved:true (T1) rendered markers BLANK on real GPU -> restored
  interleaved:false; real zoom fix is the scrollZoom/dragPan enable + NavigationControl (kept).
- [done] DEPLOY — pushed (8b272ef..b20451d; Mapbox-token allow finally registered) + Fly
  redeployed. Public verified via CDP: zoom 5.4->5.97 + nav buttons; live /#map renders 4 hubs
  + 28 cities; Batteries/Power-plants checkboxes greyed at 0 (honest empty-state, no EIA cache
  on Fly). All done.

## Log
- init — geo_data API confirmed (load_geo, county_rollup, 28 cities). EIA key still 403.
  Current initMap uses MapboxOverlay(interleaved:false) -> overlay canvas intercepts zoom/pan.
