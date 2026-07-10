"""
hedge_study.py  —  how much of a battery's future revenue should you sell forward?

THE PROBLEM (from the decade study): merchant battery revenue ranged ~4x between calm and
wild years, with 31% of everything in the top 1% of days. Lenders and owners can't live on
that. THE TOOL: sell part of the future at a fixed price — a fixed-for-floating swap (or
futures strip) settled against the hub average. Upside traded for certainty.

WHAT THIS ENGINE DOES (honest design):
  For each historical year: hedged revenue = merchant battery revenue + swap P&L, where the
  swap is SELLING Q MW flat at strike F, settling against the year's realized hub average:
      swap P&L = (F - realized_avg) * Q * hours_in_year
  Swept across hedge ratios (Q as a fraction of the battery's average discharge rate).

  STRIKE HONESTY: we do not have a decade of real futures marks (not freely public). So the
  default sets F = each year's realized average -> a ZERO-EXPECTED-P&L hedge. That isolates
  the question the desk actually asks — how much does hedging change the SHAPE (variance,
  worst year, best year) of revenue — without smuggling in a view on risk premium. A strike
  bias knob exists (bias_pct) to scenario contango/backwardation, clearly labeled.

  THE EXPECTED FINDING: a flat swap hedges the price LEVEL; the battery earns the price
  SHAPE (tails). In a Uri-type year the short hedge loses exactly when the battery wins.
  Hedging narrows the middle but caps the best years and can't protect the worst — which is
  WHY structured products (tolls, revenue floors, synthetic BESS) exist beyond plain swaps.
"""
import numpy as np
import pandas as pd


def year_table(daily_revenue: pd.DataFrame, prices: pd.Series, discharge_mwh_per_day: float):
    """Assemble per-year inputs. daily_revenue: DataFrame(date, year, revenue $ for 1 MW).
    prices: the 15-min hub series. discharge_mwh_per_day: battery's average daily discharge
    (sets the hedgeable volume; for 1 MW/2h ~1 cycle it's ~2 MWh/day)."""
    rows = []
    p = prices.dropna()
    for yr, g in daily_revenue.groupby("year"):
        yr_prices = p[p.index.year == yr]
        if not len(yr_prices):
            continue
        hours = len(yr_prices) * 0.25
        rows.append({
            "year": int(yr),
            "merchant_rev": float(g["revenue"].sum()),
            "realized_avg": float(yr_prices.mean()),
            "hours": hours,
        })
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def run_hedge_sweep(yt: pd.DataFrame, discharge_mwh_per_day: float,
                    ratios=(0.0, 0.25, 0.5, 0.75, 1.0), bias_pct=0.0):
    """Hedge-ratio sweep. Q(ratio) = ratio * (avg discharge MW-equivalent).
    Strike per year F = realized_avg * (1 + bias_pct/100)  [bias 0 => zero-mean hedge].
    Returns per-ratio stats + the per-year detail for the chart."""
    q_full = discharge_mwh_per_day / 24.0          # MW-equivalent flat volume
    out, detail = [], {}
    for r in ratios:
        q = r * q_full
        rows = []
        for _, y in yt.iterrows():
            F = y.realized_avg * (1.0 + bias_pct / 100.0)
            swap = (F - y.realized_avg) * q * y.hours          # 0 at bias 0 by construction...
            # ...per-year it is 0 ONLY if F is that year's own avg; the honest hedge is struck
            # at a common ex-ante level. Use the ACROSS-YEARS average as the ex-ante strike:
            rows.append({"year": int(y.year), "merchant": y.merchant_rev, "q_mw": q})
        # ex-ante strike: mean of realized averages across all years (a stand-in for "the
        # forward level you could have locked" absent real futures history — stated proxy)
        F0 = float(yt.realized_avg.mean()) * (1.0 + bias_pct / 100.0)
        for row, (_, y) in zip(rows, yt.iterrows()):
            row["swap_pnl"] = (F0 - y.realized_avg) * row["q_mw"] * y.hours
            row["hedged"] = row["merchant"] + row["swap_pnl"]
        d = pd.DataFrame(rows)
        out.append({
            "hedge_ratio": r,
            "mean": round(float(d.hedged.mean()), 0),
            "std": round(float(d.hedged.std()), 0),
            "worst_year": round(float(d.hedged.min()), 0),
            "best_year": round(float(d.hedged.max()), 0),
        })
        detail[r] = d
    return pd.DataFrame(out), detail, F0


def summarize(sweep: pd.DataFrame):
    m0, mF = sweep.iloc[0], sweep.iloc[-1]
    return {
        "vol_reduction_pct": round(100 * (1 - mF["std"] / m0["std"]), 1) if m0["std"] else None,
        "best_year_given_up": round(float(m0.best_year - mF.best_year), 0),
        "worst_year_change": round(float(mF.worst_year - m0.worst_year), 0),
    }


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    # Synthetic 6 "years": 5 ordinary + 1 Uri-like (battery windfall AND avg price spike)
    rng = np.random.default_rng(4)
    years = list(range(2019, 2025))
    daily_rows, price_parts = [], []
    for i, yr in enumerate(years):
        idx = pd.date_range(f"{yr}-01-01", periods=360 * 96, freq="15min")
        base = 32 + rng.normal(0, 2)
        p = base + 8 * np.sin(np.arange(len(idx)) / 96 * 2 * np.pi) + rng.normal(0, 4, len(idx))
        rev = np.maximum(rng.normal(140, 40, 360), 10.0)           # ordinary daily revenue, 1 MW
        if yr == 2021:                                              # the Uri-like year
            p[40 * 96:47 * 96] += 6000.0                            # week of $6k prices
            rev[40:47] += np.array([4000, 9000, 26000, 9000, 4000, 2000, 1000], float)
        price_parts.append(pd.Series(p, index=idx))
        for d, v in enumerate(rev):
            daily_rows.append({"date": idx[d * 96], "year": yr, "revenue": float(v)})
    daily = pd.DataFrame(daily_rows)
    prices = pd.concat(price_parts)

    yt = year_table(daily, prices, discharge_mwh_per_day=2.0)
    sweep, detail, F0 = run_hedge_sweep(yt, discharge_mwh_per_day=2.0)
    print(f"ex-ante strike proxy F0 = ${F0:.2f}/MWh (mean of realized yearly averages)\n")
    print(sweep.to_string(index=False))
    s = summarize(sweep)
    print(f"\nfull hedge vs merchant: volatility -{s['vol_reduction_pct']}%, "
          f"best year gives up ${s['best_year_given_up']:,.0f}, "
          f"worst year changes {s['worst_year_change']:+,.0f}")

    d0, d1 = detail[0.0], detail[1.0]
    uri_m = float(d0[d0.year == 2021].merchant.iloc[0])
    uri_h = float(d1[d1.year == 2021].hedged.iloc[0])
    assert uri_h < uri_m, "hedge must cap the Uri windfall (short swap loses in the spike year)"
    assert sweep.iloc[-1]["std"] < sweep.iloc[0]["std"], "hedging must reduce across-year volatility"
    assert abs(sweep.iloc[-1]["mean"] - sweep.iloc[0]["mean"]) < 0.15 * sweep.iloc[0]["mean"], \
        "zero-bias hedge shouldn't massively move the mean"
    calm = d1[d1.year != 2021]
    assert (calm.swap_pnl > 0).mean() > 0.5, "short hedge should collect in below-strike (calm) years"
    print("\nfixture self-test PASSED — hedge caps the spike year, narrows the middle, mean ~preserved")
    print("(fixture verifies the MECHANICS; the real sweep runs on the decade-study output)")
