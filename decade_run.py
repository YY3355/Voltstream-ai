"""
decade_run.py  —  assemble the decade HB_HOUSTON price series from the bundle cache
(data_archive/decade/{year}.pkl), run the Decade Study, and cache the result JSON. This is
minutes of compute (an LP per day over ~8 years x several design levers) — compute once; the
/api/decade endpoint just serves the cached JSON.
"""
import calendar
import glob
import json
import os

import numpy as np
import pandas as pd

import decade_study as DS

ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "data_archive")
DECADE_DIR = os.path.join(ARCHIVE_DIR, "decade")           # per-year price cache (gitignored)
# The 4KB summary is committed at the repo root so it ships in the image / deploy (the raw
# per-year price cache never is). Overridable via DECADE_RESULT for a volume path if desired.
RESULT_JSON = os.environ.get("DECADE_RESULT",
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "decade_result.json"))
# per-day revenue+discharge table for the hedge layer (gitignored — derived cache, ~KBs*days)
DAILY_PKL = os.environ.get("DECADE_DAILY",
                           os.path.join(ARCHIVE_DIR, "decade_daily.pkl"))

RTE = 0.88
DURATIONS = (1.0, 2.0, 4.0)
CYCLE_CAPS = (None, 1.0)
MIN_COVERAGE = 0.95

LABELS = {
    "ceiling": "Perfect-foresight CEILING (revenue upper bound). A good real-time policy captures "
               "~80% of it — see the RT engine tab.",
    "energy_only": "Energy arbitrage ONLY — ancillary-service revenue is not modeled (no public "
                   "decade of AS awards), so AS-heavy recent years are understated.",
    "nominal": "Nominal dollars (not inflation-adjusted).",
    "normalized": "Normalized to a 1 MW system -> $/MW-year; scales to any size.",
}


def load_series():
    parts = [pd.read_pickle(f) for f in sorted(glob.glob(os.path.join(DECADE_DIR, "*.pkl")))]
    if not parts:
        raise RuntimeError(f"no decade cache in {DECADE_DIR}")
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")]


def coverage_filter(s):
    """Keep years with >= MIN_COVERAGE day coverage; report the dropped partial years."""
    keep, dropped = [], []
    for yr, g in s.groupby(s.index.year):
        days = int(g.index.normalize().nunique())
        year_days = 366 if calendar.isleap(int(yr)) else 365
        pct = days / year_days
        if pct >= MIN_COVERAGE:
            keep.append(int(yr))
        else:
            dropped.append({"year": int(yr), "coverage_pct": round(100 * pct, 1), "days": days})
    keep = sorted(keep)
    fs = s[np.isin(s.index.year, keep)]
    return fs, dropped, keep


def _jsonable(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def build_decade_result():
    s = load_series()
    fs, dropped, years = coverage_filter(s)
    daily = DS.run_backtest(fs, duration_h=2.0, rte=RTE, cycle_cap=None)     # base: 2h, unlimited
    ys = DS.yearly_summary(daily)
    conc_pct, conc_k = DS.concentration_decade(daily, 0.01)
    sweep = DS.lever_sweep(fs, durations=DURATIONS, rte=RTE, cycle_caps=CYCLE_CAPS)
    fwd = DS.forward_scenarios(ys["rev_per_mw_year"].values, 10)

    # --- hedge-layer inputs (persisted for hedge_run.py) ---
    # ACTUAL average daily discharge for the 2h battery (measured, not guessed): sets the
    # hedgeable volume. Under perfect foresight + unlimited cycles this exceeds a naive
    # 1-cycle/day (~2 MWh) because volatile days cycle more than once.
    discharge_mwh_per_day = float(daily["discharge_mwh"].mean())
    # per-year realized average hub price (the swap settles against this)
    realized = {int(yr): float(g.mean()) for yr, g in fs.groupby(fs.index.year)}

    y2021 = ys[ys.year == 2021]
    sanity = {}
    if len(y2021):
        r = y2021.iloc[0]
        sanity = {"y2021_best_day": r["best_day"], "y2021_best_day_rev": float(r["best_day_rev"]),
                  "y2021_max_price": float(r["max_price_seen"]), "y2021_top10_share": float(r["top10_share_pct"])}
    yearly_records = ys.to_dict("records")
    for rec in yearly_records:                          # attach realized hub avg per year
        rec["realized_avg"] = realized.get(int(rec["year"]))

    return {
        "hub": "HB_HOUSTON",
        "years_included": years,
        "years_dropped": dropped,
        "rte": RTE, "duration_base_h": 2.0,
        "discharge_mwh_per_day": round(discharge_mwh_per_day, 3),
        "yearly": yearly_records,
        "concentration": {"top1pct_share": conc_pct, "top1pct_days": conc_k, "total_days": int(len(daily))},
        "levers": sweep,
        "forward": fwd,
        "sanity": sanity,
        "labels": LABELS,
        "source": f"real ERCOT HB_HOUSTON 15-min SPP, {years[0]}–{years[-1]} (monthly bundles)",
    }, daily


if __name__ == "__main__":
    import time
    t = time.time()
    result, daily = build_decade_result()
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(RESULT_JSON, "w") as f:
        json.dump(result, f, default=_jsonable)
    daily.to_pickle(DAILY_PKL)                                       # for the hedge layer
    print(f"decade study computed in {time.time() - t:.0f}s -> {RESULT_JSON}")
    print(f"per-day table -> {DAILY_PKL} ({len(daily)} days); "
          f"actual discharge = {result['discharge_mwh_per_day']} MWh/day (2h battery)")
    print("years included:", result["years_included"], "| dropped:", result["years_dropped"])
    print("concentration:", result["concentration"])
    print("sanity (Uri 2021):", result["sanity"])
    for row in result["yearly"]:
        print(f"  {row['year']}  ${row['rev_per_mw_year']:>10,.0f}/MW-yr  top10={row['top10_share_pct']}%  "
              f"best={row['best_day']} (${row['best_day_rev']:,.0f})  maxP=${row['max_price_seen']:,.0f}")
