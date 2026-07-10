"""
decade_study.py  —  the Decade Study: what a battery would actually have earned in ERCOT,
year by year, on real prices — and which design levers moved the money.

THREE HONEST LAYERS (never blur them):
  1. BACKTEST (fact): perfect-foresight daily dispatch on real 15-min hub prices, per year.
     Perfect foresight = the revenue CEILING for each design (label it; your RT engine showed
     a good policy captures ~80% of it). Energy arbitrage only — ancillary revenue is NOT
     modeled here (no public decade of AS awards), so recent years are understated. Say so.
  2. LEVERS (analysis): sweep what an owner controls — duration (1h/2h/4h), round-trip
     efficiency, a daily cycle cap (degradation proxy). Which knob moved revenue, on the
     record, not in theory.
  3. FORWARD (scenarios, not predictions): bootstrap the observed annual revenues into a
     10-year distribution — P10/P50/P90 cumulative. "If the future resembles the observed
     mix of years" — an assumption stated, not hidden.

The headline metric: CONCENTRATION. Share of each year's revenue earned on its top days.
Every desk knows "the money is a handful of days"; this computes it on a decade of real data.

Results normalize to a 1 MW system → $/MW-year, so they scale to any size.
"""
import numpy as np
import pandas as pd
from scipy.optimize import linprog

DT = 0.25  # 15-min


# ----------------------------- daily dispatch (fast LP) -----------------------------
def dispatch_day(prices_mwh, power_mw=1.0, duration_h=2.0, rte=0.88, cycle_cap=None):
    """Perfect-foresight energy-arbitrage dispatch for one day. Returns (revenue_$, per-interval net $).

    LP (not MILP) with a tiny simultaneity penalty: with positive prices simultaneous
    charge+discharge is never optimal; with NEGATIVE prices burning energy is genuinely
    profitable and the LP is allowed to do it — that's real ERCOT-West economics, not a bug.
    cycle_cap: max full-capacity discharges per day (degradation proxy), None = unlimited.
    """
    p = np.asarray(prices_mwh, float)
    T = len(p)
    if T < 8:
        return 0.0, np.zeros(T)
    eta = np.sqrt(rte)
    pmax = power_mw
    cap = power_mw * duration_h                      # MWh
    eps = 1e-4                                        # simultaneity discouragement, $/MW tiny
    # vars: c[0:T], d[T:2T], soc[2T:3T]; minimize -(p*(d-c)*DT) + eps*(c+d)
    obj = np.concatenate([p * DT + eps, -p * DT + eps, np.zeros(T)])
    A = np.zeros((T, 3 * T)); b = np.zeros(T)
    for t in range(T):
        A[t, 2 * T + t] = 1.0
        A[t, t] = -eta * DT
        A[t, T + t] = (1.0 / eta) * DT
        if t == 0:
            b[t] = cap / 2.0                          # start half-charged
        else:
            A[t, 2 * T + t - 1] = -1.0
    A_ub = None; b_ub = None
    if cycle_cap is not None:
        row = np.zeros(3 * T); row[T:2 * T] = DT      # total discharged MWh
        A_ub = row.reshape(1, -1); b_ub = np.array([cycle_cap * cap])
    bounds = [(0, pmax)] * T + [(0, pmax)] * T + [(0, cap)] * T
    r = linprog(obj, A_eq=A, b_eq=b, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not r.success:
        return 0.0, np.zeros(T)
    c, d = r.x[:T], r.x[T:2 * T]
    per_int = p * (d - c) * DT                        # $ per interval (1 MW system)
    return float(per_int.sum()), per_int


# ----------------------------- yearly backtest -----------------------------
def run_backtest(prices: pd.Series, duration_h=2.0, rte=0.88, cycle_cap=None):
    """Dispatch every day in a 15-min price series. Returns per-day DataFrame."""
    s = prices.dropna()
    rows = []
    for day, g in s.groupby(s.index.normalize()):
        if len(g) < 48:                               # skip badly incomplete days
            continue
        rev, _ = dispatch_day(g.values, 1.0, duration_h, rte, cycle_cap)
        rows.append({"date": day, "year": day.year, "revenue": rev, "n_int": len(g),
                     "max_price": float(g.max()), "min_price": float(g.min())})
    return pd.DataFrame(rows)


def yearly_summary(daily: pd.DataFrame, top_n=10):
    """Per-year: $/MW-year, top-days concentration, best day."""
    out = []
    for yr, g in daily.groupby("year"):
        rev = g["revenue"].sum()
        pos = g[g["revenue"] > 0]["revenue"].sort_values(ascending=False)
        top = float(pos.head(top_n).sum())
        out.append({
            "year": int(yr),
            "days": int(len(g)),
            "rev_per_mw_year": round(rev, 0),
            "top10_days_rev": round(top, 0),
            "top10_share_pct": round(100 * top / rev, 1) if rev > 0 else None,
            "best_day": str(g.loc[g["revenue"].idxmax(), "date"].date()) if len(g) else None,
            "best_day_rev": round(float(g["revenue"].max()), 0),
            "max_price_seen": round(float(g["max_price"].max()), 0),
        })
    return pd.DataFrame(out).sort_values("year")


def concentration_decade(daily: pd.DataFrame, top_frac=0.01):
    """Share of total decade revenue from the top `top_frac` of days (the headline number)."""
    rev = daily["revenue"].sort_values(ascending=False)
    total = rev.sum()
    k = max(1, int(len(rev) * top_frac))
    return round(100 * float(rev.head(k).sum()) / total, 1) if total > 0 else None, k


# ----------------------------- levers -----------------------------
def lever_sweep(prices: pd.Series, durations=(1.0, 2.0, 4.0), rte=0.88, cycle_caps=(None, 1.0)):
    """Design-lever sensitivity: annual $/MW-year by duration x cycle cap."""
    rows = []
    for d in durations:
        for cc in cycle_caps:
            daily = run_backtest(prices, duration_h=d, rte=rte, cycle_cap=cc)
            years = daily.groupby("year")["revenue"].sum()
            rows.append({"duration_h": d, "cycle_cap": cc if cc is not None else "unlimited",
                         "mean_rev_per_mw_year": round(float(years.mean()), 0),
                         "by_year": {int(y): round(float(v), 0) for y, v in years.items()}})
    return rows


# ----------------------------- forward scenarios (honest) -----------------------------
def forward_scenarios(annual_revenues, horizon_years=10, n_sims=5000, seed=7):
    """Bootstrap observed annual revenues into a horizon distribution.
    ASSUMPTION (stated, not hidden): future years drawn from the observed mix of years.
    This is a scenario tool, not a price forecast."""
    rng = np.random.default_rng(seed)
    ann = np.asarray(annual_revenues, float)
    sims = rng.choice(ann, size=(n_sims, horizon_years), replace=True).sum(axis=1)
    return {
        "horizon_years": horizon_years,
        "p10": round(float(np.percentile(sims, 10)), 0),
        "p50": round(float(np.percentile(sims, 50)), 0),
        "p90": round(float(np.percentile(sims, 90)), 0),
        "assumption": "future years resemble the observed mix of historical years (bootstrap)",
    }


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    rng = np.random.default_rng(9)
    idx_days = 120
    def make_year(start, spiky, negative=False):
        idx = pd.date_range(start, periods=idx_days * 96, freq="15min")
        hod = np.tile(30 + 10 * np.sin((np.arange(96) / 96) * 2 * np.pi - 1.2), idx_days)
        p = hod + rng.normal(0, 3, len(idx))
        if spiky:                                     # 3 monster days
            for d in (20, 60, 100):
                p[d * 96 + 68:d * 96 + 80] += 3000.0
        if negative:
            p[(np.arange(len(idx)) % 96) < 24] -= 45.0   # deep negative overnights
        return pd.Series(p, index=idx)

    calm = make_year("2021-01-01", spiky=False)
    spiky = make_year("2022-01-01", spiky=True)
    neg = make_year("2023-01-01", spiky=False, negative=True)
    prices = pd.concat([calm, spiky, neg])

    daily = run_backtest(prices, duration_h=2.0)
    ys = yearly_summary(daily)
    print(ys.to_string(index=False))
    r_calm = ys[ys.year == 2021].iloc[0]; r_spiky = ys[ys.year == 2022].iloc[0]
    assert r_spiky.rev_per_mw_year > 3 * r_calm.rev_per_mw_year, "spiky year must dominate"
    assert r_spiky.top10_share_pct > 60, f"concentration should be extreme in spike year ({r_spiky.top10_share_pct}%)"
    assert r_calm.top10_share_pct < r_spiky.top10_share_pct, "calm year less concentrated"

    conc, k = concentration_decade(daily, 0.01)
    print(f"\ndecade concentration: top 1% of days ({k} days) = {conc}% of total revenue")
    assert conc > 25, "3 monster days in 360 should dominate"

    sweep = lever_sweep(prices.loc["2022"], durations=(1.0, 2.0, 4.0), cycle_caps=(None,))
    revs = [s["mean_rev_per_mw_year"] for s in sweep]
    print("\nduration sweep (spiky year):", {s['duration_h']: s['mean_rev_per_mw_year'] for s in sweep})
    assert revs[0] <= revs[1] <= revs[2], "longer duration can't earn less under perfect foresight"

    capped = lever_sweep(prices.loc["2021"], durations=(2.0,), cycle_caps=(None, 1.0))
    assert capped[1]["mean_rev_per_mw_year"] <= capped[0]["mean_rev_per_mw_year"], "cycle cap must not increase revenue"

    fwd = forward_scenarios(ys["rev_per_mw_year"].values, 10)
    print(f"\n10y bootstrap: P10 ${fwd['p10']:,.0f}  P50 ${fwd['p50']:,.0f}  P90 ${fwd['p90']:,.0f} per MW")
    assert fwd["p10"] < fwd["p50"] < fwd["p90"]
    print("\nfixture self-test PASSED — backtest, concentration, levers, scenarios all sane")
    print("(fixture verifies the MATH on synthetic years; the real decade runs on the Mac archive)")
