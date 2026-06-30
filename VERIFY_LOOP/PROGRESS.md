# Progress

- [done]  T1: add `/api/qse` endpoint to app.py (+ commit qse_loop.py it depends on)
- [done] T2: add QSE panel 11 (#c-qse) + qse() renderer (2 charts) to dashboard_live.html
- [done] T3: final end-to-end verify (curl warm + headless-Chrome render)

## Log
- T1: verified via curl in `volt`. /api/qse http=200, ~0.5s (greedy heuristic, no LP -> fast).
  n_paths 200, coord_gain_pct 109.0, commit_err_2h 40.9977 (lag_curve monotonic 0->7->13.3->24.3->41,
  pct_of_fresh 100->99.1), coupled_spike 0.387 > power_spike 0.185, illustration 3x96 traces. Sane.
- T2+T3: verified in `volt`. Warmed /api/qse (http 200), headless-Chrome render of /
  shows panel 11 populated: +109% hero, 2h-stale 41.0 MWh, spike $0.39/$0.18; lag chart
  (orange err-vs-age curve) + coord chart (price area + coupled/power-only SoC traces) both
  present; 4-entry legend. No placeholder. Note: coupled_rev $0.70 < power_only_rev $0.76 is
  expected/honest (power-only spends broadly for more TOTAL rev but misses concentrated spikes).
