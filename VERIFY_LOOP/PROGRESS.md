# Progress

- [done]  T1: rename title/masthead/tagline
- [done]  T2: /api/journal endpoint (empty state) + verify curl
- [done]  T3a: nav bar + 6 empty sections + tab-switch/hash-routing JS; all panels initially under Co-Pilot
- [done]  T3b: MOVE Asset Opt panels (Bolt #c-dp, coopt, vpp) into Asset Opt section (verify ask still lights Bolt)
- [done]  T3c: MOVE Trading Desk panels (rt, dart) into Trading Desk section
- [done]  T3d: MOVE Quant panels (curve, swap, risk, qse) into Quant section
- [done]  T3e: MOVE Learning Lab panel (dcopf) into Learning section
- [done]  T3f: lazy-load wiring — bare auto-calls -> per-section loaders (fire on first open); + status strip
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
