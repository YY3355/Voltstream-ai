# Goal
Restructure dashboard_live.html from one scroll into the unified VoltStream platform:
top nav + six show/hide sections, heavy tabs lazy-load on first open. MOVE existing
panel markup + JS intact (don't rewrite). Add /api/journal + a new P&L panel.

## Section → panel mapping (MOVE, don't rewrite)
- Co-Pilot        : panels 1-4 (router/forecast/bolt/RAG) + verdict + brief + askbar/chips
                    + a thin system-status strip (reuse /api/state values, no new endpoint)
- Asset Optimization: panel 5 co-optimization (Bolt/MILP engine), panel 6 VPP
- Trading Desk    : panel 7 RT engine, panel 12 DART, + NEW P&L panel (/api/journal)
- Quant & Structuring: panel 8 forward curve, 9 swap, 10 risk, 11 QSE
- Learning Lab    : panel 13 DCOPF
- About           : honest-scope page (live data + real methodology vs illustrative levels /
                    simulated telemetry vs NOT live trading)

## Loader refactor (CRITICAL)
Currently bare auto-run at page load: init(); coopt()+setInterval(coopt,60000); vpp(); rt();
curve(); swap(); risk(); qse(); dart(); dcopf().
Refactor the CALLS (not the functions) into a per-section lazy loader registry: each section's
loader runs ONCE on first open. Co-Pilot loads on page load (landing tab). coopt's 60s interval
starts on first Asset-Opt open. Implement location.hash routing (#assetopt/#trading/#quant/
#learning/#about) so each tab is deep-linkable AND independently renderable in headless Chrome.

## New API
/api/journal reads journal/ledger.csv -> {cum_series, total_pnl, hit_rate_pct, n_days, by_hub}.
ledger.csv does NOT exist yet -> honest empty state:
  {"n_days": 0, "note": "no settled days yet — first settlement 2026-07-05"}
P&L panel renders that empty state cleanly; header (not a footnote) carries:
  "paper book — calls committed in advance (git-audited), no execution/fees".

## Masthead / title
title + masthead -> "VoltStream — agentic co-pilot for ERCOT battery trading"
tagline -> "the math makes the decisions, the AI explains them."

## Tasks (granular, each commit green; DOM move is atomic so isolated in its own commit)
- T1: rename title/masthead/tagline only
- T2: /api/journal endpoint (empty state) — verify curl
- T3: nav + section machinery + lazy-loader registry + hash routing; MOVE all panels into the
      six sections; convert every bare auto-call into its section loader (About = stub)
- T4: NEW P&L panel in Trading Desk rendering the journal empty state + header line
- T5: About honest-scope content
- T6: final full verify

## How to verify (every iteration) — recipe from project memory (no CLAUDE.md in repo)
`volt` conda env. Kill stale :8020 first, wait for NEW instance (200 on /openapi.json).
Warm heavy caches first: curl /api/dart and /api/risk (dart cached on disk + pre-warmed; risk ~15s).
Start: ERCOT_LIVE=0 ERCOT_DATA_DIR=data_clean conda run -n volt python -m uvicorn app:app --port 8020
  NB: ERCOT_LIVE=0 is REQUIRED — without it get_prices() does a live pull (~71 pts, < one full
  day) and /api/state (forecast/coopt/vpp/rt) 500s on empty `full`. DART is unaffected (its
  fetch_live hits gridstatus directly regardless of ERCOT_LIVE). Task's start cmd omitted it.
Checks:
  - curl EVERY /api endpoint still 200: state, cooptimize, vpp, rt, curve, swap, risk, qse,
    dart, dcopf, journal (+ POST ask).
  - headless-Chrome render EACH tab via hash (/, /#assetopt, /#trading, /#quant, /#learning,
    /#about); confirm that tab's panels populate.
  - render `/` (Co-Pilot only) and confirm NO auto-loader fired for unopened tabs (heavy panel
    placeholders like #dart-hero/#risk-hero/#dcopf-hero still show their "…" placeholder text).

## Guardrails
- Supervised. Max 15 iterations. One task = one commit. Never commit red / a broken panel.
