# Progress

- [done]  T1: rename title/masthead/tagline
- [doing] T2: /api/journal endpoint (empty state) + verify curl
- [todo]  T3: nav + section machinery + lazy loaders + hash routing + MOVE all panels into 6 sections
- [todo]  T4: NEW P&L panel in Trading Desk (journal empty state + header line)
- [todo]  T5: About honest-scope content
- [todo]  T6: final full verify (all /api 200 + every tab renders + no leakage)

## Notes
- Loaders today (bare, page-load): init(); coopt()+setInterval(coopt,60000) @419; vpp() @454;
  rt() @497; curve() @550; swap() @590; risk() @644; qse() @709; dart() @790; dcopf() @882.
- Endpoints: /api/state, POST /api/ask, /api/cooptimize, /api/vpp, /api/rt, /api/curve,
  /api/swap, /api/risk, /api/qse, /api/dart, /api/dcopf (+ new /api/journal).
- Interpretation: "Bolt" in Asset Optimization = the co-optimization engine (panel 3 "Bolt
  Optimizer" stays in Co-Pilot per "panels 1-4"). Flag at check-in.

## Log
- HARNESS FIX: must start server with ERCOT_LIVE=0 (task cmd omitted it). Without it,
  get_prices() live-pulls ~71 pts (<96) and /api/state 500s (full[-1] on empty). DART
  unaffected. Updated GOAL.md verify command.
- T1: verified with ERCOT_LIVE=0 — /api/state 200 (1.1s); headless render shows new masthead
  "VoltStream" + tagline, forecast + bolt panels populate; all 13 cards present; old brand gone.
