# GOAL — Independent scoring of Kardashev Labs' RT-DA spread forecasts

A third-party audit artifact: score Kardashev's published spread forecasts through OUR existing harness,
using OUR verified settlement record as ground truth. Shared with Ashutosh (Kardashev) for factual
review before anything public. Supervised loop, max 8 iterations, ONE task = ONE commit, pause + report
each. Never commit red; 3x same red = blocked, stop.

## SCOPE
- **In:** `research/kardashev_eval/` + ONE tiny capture addition (Task 5).
- **Out (HARD):** NO harness changes, NO `signal.py`, NO deploy, NO UI.

## HARD CONSTRAINTS (violating any = RED)
1. **INDEPENDENCE IS THE PRODUCT.** Realized DA/RT prices come from OUR verified stores
   (`locational/` + `dam_decade/` + `price_store`), NEVER from their API. We score their forecasts
   against our settlement record.
2. **SIGN CONVENTION GATE.** Their target = "RT-DA spread"; ours = `dart = DA − RT`. Establish the
   mapping EMPIRICALLY before any scoring — reconstruct 3 known days from raw prices both ways and match
   against their published values. A sign flip silently inverts every result; this check BLOCKS all
   downstream tasks.
3. **Timing honesty.** Score ONLY forecasts whose published-at precedes delivery, per their API's own
   timestamps. Attest only to "what their API serves + claims" — the note says "as served by their API
   on <fetch date>", no stronger. Fetch once, FREEZE the snapshot as a committed artifact; scoring runs
   on the frozen copy.
4. **Small-sample honesty.** Live window ~weeks. Report n (node-hours, days, events) beside every metric;
   NO significance claims; spike-head metrics only where events >= 5, else "insufficient events (k)".
5. **Apples-to-apples.** Score only hubs/zones overlapping our verified coverage (the 4 hubs; note which
   of their 15 locations are unscored + why). Compare vs OUR baselines (climatology, zero-spread,
   persistence) on the SAME dates/hours/locations — never our model's walk-forward numbers from other
   periods as head-to-head.
6. **COURTESY GATE.** The note is DRAFT — shared with Ashutosh for factual review before Mike posts
   anything public. The loop NEVER publishes.
7. **No LLM in the scoring path.**

## TASKS
1. **Fetch + freeze.** Pull `/forecast/spread/history` (fall back to asking Mike for the CSV if the API
   fights us); store raw as `research/kardashev_eval/snapshot_<date>/`; document schema (quantiles,
   locations, timestamps, timezone). Report span/n/quantile set BEFORE designing further.
2. **Sign + alignment gate** (constraint 2): empirical mapping proof on 3 days; pin timezone + hour-
   ending vs hour-beginning vs our stores. STOP and show the mapping evidence.
3. **Join + score.** Their quantiles through our metrics on overlapping locations/hours: pinball per
   published quantile, empirical coverage vs their 80% target (P10-P90), + our baseline suite on
   identical coordinates. Checker hand-rederives one location-day pinball + one coverage count.
4. **Tail focus.** Coverage + pinball split by regime — calm vs top-decile |spread| hours; does clip-
   then-widen hold coverage in the tail or only on average? Reliability bins where events permit.
5. **Capture rhythm addition.** Tiny daily job fetching their `/latest` into our archive (vintage =
   their published-at + our capture UTC) — from today forward we hold an independently-witnessed record.
   Wire into jobs.jsonl + watchdog, DRY_RUN tested, enablement in the final handoff.
6. **DRAFT note.** `research/kardashev_eval/NOTE.md` — method, independence statement, sign/alignment
   proof, results tables with n's, tail finding, limitations. Written so Ashutosh can check every number.
   Marked DRAFT — NOT FOR PUBLICATION until both Mike and Ashutosh clear it.

## When done
STOP with the note + what to send Ashutosh.
