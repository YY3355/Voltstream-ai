# DART paper book — ledger regime

**One book, one rule, honestly labeled.** Rule: trailing 10-day hour-of-day DART bias, threshold
$1/MWh, 1 MW clips (`dart_journal.py build_calls`). Settlement is pure arithmetic against realized
DA-RT prices (`score_calls`) appended to `ledger.csv` (immutable, tracked in git).

| Period | Execution | Provenance stamps in each `calls_*.json` |
|---|---|---|
| through **2026-07-22** | the rule, run **manually** | none (pre-stamp) |
| from **2026-07-24** on | the **same rule**, **auto-committed** 16:00 ET (launchd) | `model_version` (git SHA of signal-logic files), `generated_by:"auto"`, `generated_at` (UTC ISO) |

- `model_version` = combined git blob SHA of the signal-logic files (`dart_journal.py` +
  `dart_engine.py`) at generation time — changes iff the rule or its data source changes.
- Already-pushed history is **never rewritten**; stamps apply **going forward** (07-26+). The 07-24 /
  07-25 files stay exactly as committed.
- **Not real trading:** virtual fills at settlement, no execution / fees / credit / risk limits. A
  discipline record — evidence of process, not a profit claim.
- **Never backdate:** a commit-leg run after its valid window logs a MISSED day; settle only settles
  days whose realized data exists. Git timestamps stay meaningful.
