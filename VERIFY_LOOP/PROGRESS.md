# Progress — ERCOT DART Map tab (Mapbox GL + deck.gl, no build)

Max 12 iterations. Supervised.

## Tasks
- [done] T1 — /api/map endpoint. Verified: map_data fixture PASSES; /api/map 200 (0.02s warm)
  with 4 live hub points, TX center, window/data_source/note. commit ce39aca.
- [done] T2+T3 — Map tab (Mapbox GL v3.9.0 + deck.gl v9.0.35 CDN, lazy). Verified headless:
  dark TX basemap + 4 green hub circles placed correctly, map-meta "4 hubs plotted" +
  source/window, honest-scope ON map, 2 canvases, tooltip wired. Lazy-load clean (map not
  init on /). Existing untouched: state 200 (canonical env), quant hedge+decade render, all
  endpoints 200. commit 76e34b2.
- [done*] DEPLOY — Fly redeployed; public /api/map 200 (4 live hubs); public /#map renders
  full labeled TX basemap + 4 correctly-placed green circles (Dallas/San Angelo/San Antonio/
  Houston), on-map scope, meta. GitHub push BLOCKED by push-protection (Mapbox pk. token at
  dashboard_live.html:1251); user chose "allow via GitHub URL" — push pending their unblock click.

## Log
- init — APIs confirmed (run_dart stats shape, build_map output). Nav/section/LOADERS/_loaded
  lazy-load mechanism understood (SECTIONS@1015, LOADERS@1212, openSection@1218).
