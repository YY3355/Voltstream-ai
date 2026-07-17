# Progress — Phase 3 (locational decade revenue + year playback)

Max 12 iterations. Supervised.

## Tasks
- [done] T1 — locational_run.py (4-hub bundle extract). Verified: fixture PASSES; 8yrs x 4 hubs,
  0 dropped; Houston cross-check vs decade cache = 280,477 intervals, max diff $0.0000; 2021 Uri
  every hub (maxP ~$9k, top10 ~60%, best 2021-02-15 ~$31k). 11KB JSON committed. commit fa372c8.
- [done] T2 — /api/locational endpoint + .dockerignore un-exclude. Verified 200 (7ms), 8yrs x
  4 hubs, rev scale + mean_by_hub + labels. commit bce56e1.
- [done] T3+T4 — year playback (slider+play, fixed teal->red scale, hub year popup) + honest
  labels verbatim + NO flow arcs. Verified CDP: 8yrs x 4 hubs, off-by-default, scrub 2020->2021
  spikes radius 24->57, popup year detail, 4 labels present, no arc layer; screenshot confirms
  2021 Uri drama. Other layers/tabs untouched. commit 2a43205.
- [done] DEPLOY — pushed (44ce9ab..d68ed90) + Fly redeployed. Public /api/locational 200 (8yrs
  x 4 hubs). Public CDP: scrub 2020->2021 spikes 24->57, popup+labels+noArcs all pass, ok=true;
  live 2021 screenshot shows hot-amber revenue circles + playback panel. ALL DONE.

## Log
- init — API confirmed. Cached decade pkls are SINGLE-HUB Houston; raw bundles NOT on disk ->
  must re-download bundles, parse all 4 hubs per download. 4 hub coords in map_data.HUB_POINTS.
  Plan: reuse bundle_to_hub_series(zip_bytes,hub) on once-downloaded bytes (or single-pass
  multi-hub parser); cross-check Houston output vs existing 2021.pkl.
