"""
hedge_run.py  —  run the hedge sweep (hedge_study.py) on the REAL decade-study output and
cache a small summary JSON for /api/hedge. Reads the per-day revenue table + the reassembled
hub price series produced by decade_run.py; uses the ACTUAL measured daily discharge as the
hedgeable volume. Compute is trivial (the LP-heavy work already lives in the decade cache), so
this can rerun cheaply whenever decade_run.py regenerates its inputs.
"""
import json
import os

import pandas as pd

import hedge_study as HS
from decade_run import ARCHIVE_DIR, DAILY_PKL, RESULT_JSON, load_series, coverage_filter

RATIOS = (0.0, 0.25, 0.5, 0.75, 1.0)
BIAS_PCT = 0.0                                    # zero-expected-P&L hedge (no risk-premium view)
HEDGE_JSON = os.environ.get("HEDGE_RESULT",
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), "hedge_result.json"))

LABELS = {
    "strike_proxy": "Strike is a STATED PROXY: the across-years mean of realized hub averages "
                    "(a stand-in for the forward level you could have locked). There is no free "
                    "public decade of ERCOT futures marks, so no real strip is used.",
    "zero_ep": "Zero expected P&L by construction (bias 0) — this isolates how hedging changes "
               "the SHAPE of revenue (variance, tails), not a bet on risk premium.",
    "merchant": "Merchant revenue underneath is the perfect-foresight energy-arbitrage CEILING "
                "from the Decade Study (1 MW, 2h, energy-only).",
    "energy_only": "Energy arbitrage only — ancillary services not modeled.",
    "advice": "Analysis, not advice.",
}


def _daily_table():
    """Per-day revenue table from the decade cache (regenerate via decade_run.py if missing)."""
    if os.path.exists(DAILY_PKL):
        return pd.read_pickle(DAILY_PKL)
    raise RuntimeError(f"missing {DAILY_PKL} — run `python decade_run.py` first")


def build_hedge_result():
    decade = json.load(open(RESULT_JSON))
    discharge = float(decade["discharge_mwh_per_day"])          # ACTUAL measured (T1)
    daily = _daily_table()

    # reassemble the same real hub series the decade study ran on, restricted to kept years
    s = load_series()
    fs, _dropped, years = coverage_filter(s)

    yt = HS.year_table(daily, fs, discharge_mwh_per_day=discharge)
    sweep, detail, F0 = HS.run_hedge_sweep(yt, discharge_mwh_per_day=discharge,
                                           ratios=RATIOS, bias_pct=BIAS_PCT)
    summ = HS.summarize(sweep)

    # minimum-variance ratio: lowest across-year std over the swept ratios
    sweep_recs = sweep.to_dict("records")
    minvar = min(sweep_recs, key=lambda r: r["std"])
    interior = 0.0 < minvar["hedge_ratio"] < 1.0

    # per-year merchant vs hedged at full hedge (ratio 1.0) for the bar chart
    full = detail[1.0]
    per_year = [{"year": int(r.year), "merchant": round(float(r.merchant), 0),
                 "hedged": round(float(r.hedged), 0), "swap_pnl": round(float(r.swap_pnl), 0)}
                for r in full.itertuples()]

    uri = [y for y in per_year if y["year"] == 2021]
    uri_capped = bool(uri and uri[0]["hedged"] < uri[0]["merchant"])

    return {
        "hub": decade.get("hub", "HB_HOUSTON"),
        "years": years,
        "discharge_mwh_per_day": round(discharge, 3),
        "hedge_mw_full": round(discharge / 24.0, 4),           # MW-equivalent flat volume at ratio 1
        "strike_proxy_usd_mwh": round(float(F0), 2),
        "bias_pct": BIAS_PCT,
        "ratios": list(RATIOS),
        "sweep": sweep_recs,                                    # per-ratio mean/std/worst/best
        "min_variance": {"hedge_ratio": minvar["hedge_ratio"], "std": minvar["std"],
                         "interior": interior},
        "per_year_full_hedge": per_year,
        "summary": summ,                                        # vol_reduction, best given up, worst change
        "sanity": {"uri_hedged_lt_merchant": uri_capped,
                   "uri_merchant": uri[0]["merchant"] if uri else None,
                   "uri_hedged": uri[0]["hedged"] if uri else None},
        "takeaway": "a flat swap hedges the level, not the tails — the residual is why "
                    "structured products exist.",
        "labels": LABELS,
        "source": decade.get("source", ""),
    }


if __name__ == "__main__":
    import time
    t = time.time()
    res = build_hedge_result()
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(HEDGE_JSON, "w") as f:
        json.dump(res, f)
    print(f"hedge sweep computed in {time.time() - t:.0f}s -> {HEDGE_JSON}")
    print(f"strike proxy F0 = ${res['strike_proxy_usd_mwh']}/MWh | "
          f"full hedge volume = {res['hedge_mw_full']} MW ({res['discharge_mwh_per_day']} MWh/day)")
    mv = res["min_variance"]
    print(f"min-variance ratio = {mv['hedge_ratio']} (interior={mv['interior']}, std=${mv['std']:,.0f})")
    print("sweep (ratio -> mean / std / worst / best):")
    for r in res["sweep"]:
        print(f"  {r['hedge_ratio']:>4}  mean ${r['mean']:>10,.0f}  std ${r['std']:>10,.0f}  "
              f"worst ${r['worst_year']:>10,.0f}  best ${r['best_year']:>10,.0f}")
    s = res["sanity"]
    print(f"SANITY Uri 2021: merchant ${s['uri_merchant']:,.0f} -> hedged ${s['uri_hedged']:,.0f}  "
          f"capped={s['uri_hedged_lt_merchant']}")
    print(f"summary: {res['summary']}")
