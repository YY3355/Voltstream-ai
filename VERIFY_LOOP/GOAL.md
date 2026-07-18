# GOAL — finish Phase 3: (A) live alerts, (B) animated flow, (C) intraday playback

Three tasks, commit each. alert_engine.py fixture-tested.

## APIs / facts
- `alert_engine.run_alerts(dart, weather, constraints)` -> {alerts[], n, max_severity, context,
  note}; alert: id/source/severity(info<watch<alert)/threshold/value/detail/rationale.
  Inputs: dart = run_dart() (has stats{hub:{mean}}, basis{pair:{last/mean}}); weather =
  run_weather() (signal.wind_belt_avg_mph); constraints = LIVE build_arcs output ({arcs[],
  unplaced[]} each with shadow_price/constraint) — NOT the 90d aggregate.
- Snapshot flow arcs (build_arcs) carry direction + flow_mw + utilization + type=
  reported_constraint_flow. The 90d AGGREGATE arcs do NOT (no measured instantaneous direction).
- Intraday: data_archive/constraints/sced_90d.pkl has a full recent day 2026-07-16 (290 SCED
  snapshots). Augmented registry (GIS + crosswalk.json) resolves placeable stations.

## Tasks
- **A ALERTS** /api/alerts: assemble live inputs (run_dart, run_weather, live build_arcs) ->
  run_alerts(). Map-tab alerts bell/badge: count colored by max_severity (info/watch/alert),
  list each fired alert's detail + rationale VERBATIM, honest empty-state ("no thresholds
  crossed — conditions calm"). Poll on a sane interval (e.g. 60s), not a tight loop.
- **B ANIMATED FLOW** animate particles along the EXISTING measured snapshot arcs ONLY
  (type=reported_constraint_flow) in the MEASURED flow direction ('direction'/flow sign);
  requestAnimationFrame; speed/density scale with utilization. HARD RULE: animate ONLY arcs
  from real from/to/flow — NO new arcs, NO estimated flows, nothing between hubs/regions/any
  pair without measured flow. The 90d aggregate arcs (no direction) do NOT animate.
- **C INTRADAY PLAYBACK** from archived NP6-86-CD snapshots: a time scrubber that replays one
  recent day's constraint evolution (which lines binding through the day). Reuse the snapshot-
  arc rendering (which animates via B); drive it from the selected timestamp. Label "replay of
  real SCED snapshots." Ship a small intraday_result.json (committed) so it works on Fly.

## Definition of done
- /api/alerts 200 with real evaluation; badge reflects real conditions; empty-state honest.
- Particles animate ONLY on measured snapshot arcs (live/intraday), never the aggregate/hubs.
- Intraday scrubber replays real per-SCED snapshots of a recent day.
- Other layers (hubs/batteries/plants/cities/weather/county/locational/constraints) + tabs
  untouched. Pushed when green; redeploy Fly.

## Verify (CDP)
- alert fixture PASSES; curl /api/alerts -> 200 real context/alerts.
- CDP: alert badge count+color matches /api/alerts; particle positions advance over rAF frames
  and exist ONLY for flow arcs (assert none for aggregate/other layers); scrubber changes the
  rendered snapshot arcs across timestamps; existing tabs render.

## Guardrails
- Max 15 iterations. Supervised. One task = one commit. Green commits only.
- HARD RULE (B): measured arcs only, never fabricate a flow/arc. Sane poll interval (no tight
  loop). NEVER commit data caches/secrets; only small committed *_result.json summaries.
