# Progress

- [done]  T1: add `/api/qse` endpoint to app.py (+ commit qse_loop.py it depends on)
- [doing] T2: add QSE panel 11 to dashboard_live.html (2 charts), verify page renders
- [todo]  T3: final end-to-end verify (curl + page render)

## Log
- T1: verified via curl in `volt`. /api/qse http=200, ~0.5s (greedy heuristic, no LP -> fast).
  n_paths 200, coord_gain_pct 109.0, commit_err_2h 40.9977 (lag_curve monotonic 0->7->13.3->24.3->41,
  pct_of_fresh 100->99.1), coupled_spike 0.387 > power_spike 0.185, illustration 3x96 traces. Sane.
