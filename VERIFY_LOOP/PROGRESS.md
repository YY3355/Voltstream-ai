# Progress — Phase 3 finish: alerts + animated flow + intraday playback

Max 15 iterations. Supervised.

## Tasks
- [done] A — /api/alerts + Map alert strip. Verified: fixture PASSES; /api/alerts 200 real eval
  (1 info now); CDP strip sev-class+count match API, detail+rationale verbatim, empty-state+note.
  Poll 60s. commit 080e21d.
- [done] B — particle flow on measured snapshot arcs only (rAF, measured direction, density/
  speed by utilization). Verified CDP: aggregate=0 particles/no layer; live-now=10 particles +
  __flowT advancing + measured-only; off=0. HARD RULE holds. commit 52240b9.
- [done] C — intraday replay: /api/intraday (244 runs/2026-07-16, 123 w/ arcs, 73KB committed)
  + scrubber (slider+play) reusing snapshot-arc rendering + B's particles. Verified CDP: scrub
  matches API frames exactly (02:20=1,02:30=2), particles animate measured-only, replay label.
  commit 671290b.
- [done] DEPLOY — pushed (468650c..a00bd27) + Fly redeployed. Public verified via CDP: A alerts
  ok (1 info, verbatim), B flow ok (agg 0 particles / live 10 advancing), C intraday ok (244
  snapshots, frames match, particles animate). ALL DONE.

## Log
- init — alert fixture PASSES. run_dart has stats+basis; run_weather has signal. Alert
  constraints input = LIVE build_arcs (arcs+unplaced w/ shadow_price), not aggregate. Snapshot
  arcs carry direction/flow/type=reported_constraint_flow (animatable); aggregate does not.
  Intraday day 2026-07-16 = 290 snapshots in sced_90d.pkl.
