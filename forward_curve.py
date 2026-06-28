"""
forward_curve.py  —  electricity forward curve construction (desk methodology).

A power forward curve is what every electricity trading desk marks positions against.
It is built in three real steps:

  1. BLOCKS.   Futures trade as monthly/quarterly/calendar blocks, each split into
               on-peak (ERCOT 5x16: Mon-Fri, hours ending 0700-2200) and off-peak.
  2. BOOTSTRAP. Overlapping quotes must be arbitrage-free: a quarter must equal the
               hour-weighted average of its months. We solve for any implied month so
               every quoted block is internally consistent. (No free lunch in the curve.)
  3. SHAPING.  Monthly peak/off-peak levels are shaped down to an HOURLY forward curve
               using a historical hour-of-day profile, normalized so the shaped hours
               re-aggregate EXACTLY back to the block levels. (Shape from history, level
               from the market — standard desk practice.)

HONEST SEAM: the methodology is desk-grade and the SHAPE is real ERCOT history. The
forward LEVELS here are an illustrative strip — drop in real CME ERCOT futures settlements
and the same machine produces a live, market-calibrated curve. Nothing about the math
changes; only the input source does.
"""
import numpy as np
import pandas as pd


# ----------------------------- peak / off-peak -----------------------------
def is_onpeak(idx: pd.DatetimeIndex) -> np.ndarray:
    """ERCOT 5x16 on-peak: Monday-Friday, clock hours 06:00-21:59 (HE 0700-2200)."""
    idx = pd.DatetimeIndex(idx)
    weekday = idx.weekday < 5
    inhours = (idx.hour >= 6) & (idx.hour <= 21)
    return np.asarray(weekday & inhours)


# ----------------------------- historical shape -----------------------------
def historical_shape(prices: pd.Series):
    """Average price by hour-of-day, split weekday/weekend -> a normalized shape profile.

    Returns a function shape(hour, is_weekend) giving a *relative* factor, plus the raw
    hour-of-day means for inspection. Levels are stripped out; only the shape remains.
    """
    s = prices.dropna()
    df = pd.DataFrame({"y": s.values}, index=pd.DatetimeIndex(s.index))
    df["hour"] = df.index.hour
    df["wknd"] = df.index.weekday >= 5
    prof = df.groupby(["wknd", "hour"])["y"].mean()
    # fall back to overall hour mean if a (wknd,hour) cell is missing
    hour_mean = df.groupby("hour")["y"].mean()
    overall = float(df["y"].mean())

    def raw(hour, wknd):
        if (wknd, hour) in prof.index:
            return float(prof.loc[(wknd, hour)])
        if hour in hour_mean.index:
            return float(hour_mean.loc[hour])
        return overall

    return raw, prof


# ----------------------------- bootstrap -----------------------------
def bootstrap_blocks(quotes, months):
    """Solve for arbitrage-free monthly peak & off-peak levels from quoted blocks.

    quotes : list of dicts, each {'months': [ 'YYYY-MM', ... ], 'peak': p, 'offpeak': o}
             A single-month quote fixes that month; a multi-month (quarter/cal) quote
             constrains the hour-weighted average of its months.
    months : ordered list of 'YYYY-MM' the curve should cover.

    Returns {month: {'peak': x, 'offpeak': y}} consistent with every quote
    (least-squares if over/under-determined), with on/off-peak hour weights per month.
    """
    m_idx = {m: i for i, m in enumerate(months)}
    wk_pk, wk_op = _month_hour_weights(months)  # on/off-peak hour counts per month

    def solve(side, wts):
        A, b = [], []
        for q in quotes:
            if side not in q:
                continue
            row = np.zeros(len(months))
            tot = sum(wts[m_idx[m]] for m in q["months"])
            for m in q["months"]:
                row[m_idx[m]] = wts[m_idx[m]] / tot
            A.append(row); b.append(q[side])
        A, b = np.array(A), np.array(b)
        x, *_ = np.linalg.lstsq(A, b, rcond=None)
        return x

    xpk, xop = solve("peak", wk_pk), solve("offpeak", wk_op)
    return {m: {"peak": float(xpk[i]), "offpeak": float(xop[i])} for m, i in m_idx.items()}


def _month_hour_weights(months):
    """Hours of on-peak and off-peak in each month (for hour-weighted block math)."""
    pk, op = [], []
    for m in months:
        start = pd.Timestamp(m + "-01")
        end = start + pd.offsets.MonthBegin(1)
        hrs = pd.date_range(start, end, freq="h", inclusive="left")
        on = is_onpeak(hrs)
        pk.append(int(on.sum())); op.append(int((~on).sum()))
    return np.array(pk, float), np.array(op, float)


# ----------------------------- shaping to hourly -----------------------------
def shape_to_hourly(blocks, raw_shape, months):
    """Shape monthly peak/off-peak levels into an HOURLY forward curve.

    For each month, hours are scaled by the historical shape, normalized separately over
    on-peak and off-peak hours so the shaped hours average EXACTLY to the block level.
    """
    rows = []
    for m in months:
        start = pd.Timestamp(m + "-01")
        end = start + pd.offsets.MonthBegin(1)
        hrs = pd.date_range(start, end, freq="h", inclusive="left")
        on = is_onpeak(hrs)
        wknd = hrs.weekday >= 5
        shp = np.array([raw_shape(h.hour, bool(w)) for h, w in zip(hrs, wknd)])
        out = np.zeros(len(hrs))
        for mask, level in ((on, blocks[m]["peak"]), (~on, blocks[m]["offpeak"])):
            if mask.sum() == 0:
                continue
            seg = shp[mask]
            seg = seg / seg.mean() if seg.mean() != 0 else np.ones_like(seg)
            out[mask] = level * seg          # averages to `level` over the segment by construction
        rows.append(pd.Series(out, index=hrs))
    curve = pd.concat(rows)
    curve.name = "forward_$mwh"
    return curve


# ----------------------------- verification -----------------------------
def verify_reaggregation(curve, blocks, months, tol=1e-6):
    """Confirm shaped hourly curve re-aggregates to the input block levels (no leakage)."""
    ok = True
    for m in months:
        seg = curve[curve.index.to_period("M").astype(str) == m]
        on = is_onpeak(seg.index)
        pk = seg[on].mean(); op = seg[~on].mean()
        if abs(pk - blocks[m]["peak"]) > tol or abs(op - blocks[m]["offpeak"]) > tol:
            ok = False
    return ok


# ----------------------------- swap valuation -----------------------------
def value_swap(curve, strike, volume_mw, start=None, end=None, product="7x24"):
    """Mark-to-market of a fixed-for-floating power swap against the forward curve.

    A fixed-for-floating swap exchanges a fixed strike ($/MWh) for the floating
    (forward) price over a delivery period. From the fixed-PAYER's perspective
    (pays fixed, receives floating), the position gains when the forward floats
    above the strike:

        MtM = (forward_avg - strike) * volume_mw * hours_in_period

    Parameters
    ----------
    curve   : hourly forward curve (pd.Series indexed by timestamp), $/MWh.
    strike  : fixed price, $/MWh.
    volume_mw : notional power, MW (constant over the period).
    start, end : 'YYYY-MM' delivery window (inclusive of both months); default = full curve.
    product : which hours settle — '7x24' (around-the-clock), 'peak' (5x16), or 'offpeak'.
    """
    c = curve
    if start is not None:
        c = c[c.index >= pd.Timestamp(start + "-01")]
    if end is not None:
        end_excl = pd.Timestamp(end + "-01") + pd.offsets.MonthBegin(1)
        c = c[c.index < end_excl]
    on = is_onpeak(c.index)
    if product == "peak":
        c = c[on]
    elif product == "offpeak":
        c = c[~on]
    hours = int(len(c))
    forward_avg = float(c.mean()) if hours else 0.0
    notional_mwh = float(volume_mw) * hours
    basis = forward_avg - float(strike)           # floating minus fixed
    mtm = basis * notional_mwh                     # fixed-payer perspective
    return {
        "strike": float(strike),
        "volume_mw": float(volume_mw),
        "product": product,
        "forward_avg": forward_avg,
        "hours": hours,
        "notional_mwh": notional_mwh,
        "basis": basis,
        "mtm": mtm,
    }


# ----------------------------- top-level demo -----------------------------
def build_forward_curve(data_dir="data", illustrative=True):
    """Build an hourly forward curve: real historical shape + (illustrative) forward levels."""
    from ercot_data import load_prices
    hist = load_prices(data_dir)
    raw_shape, prof = historical_shape(hist)

    # ----- forward LEVELS -----
    # Illustrative strip (swap for CME ERCOT futures settlements to go live). Anchored to the
    # data's own recent peak/off-peak level so it isn't arbitrary, with a mild seasonal lift.
    on = is_onpeak(hist.index)
    base_pk = float(hist[on].mean()); base_op = float(hist[~on].mean())
    start_month = (hist.index.max().to_period("M") + 1).strftime("%Y-%m")
    months = [(pd.Period(start_month) + i).strftime("%Y-%m") for i in range(6)]
    season = [1.00, 1.06, 1.18, 1.30, 1.15, 1.02]  # summer-peaking shape, illustrative
    quotes = []
    for m, k in zip(months, season):
        quotes.append({"months": [m], "peak": round(base_pk * k, 2), "offpeak": round(base_op * k, 2)})
    # add a quarter quote to exercise the bootstrap (must reconcile with its months)
    q_months = months[1:4]
    wk_pk, _ = _month_hour_weights(q_months)
    q_peak = float(np.average([quotes[i + 1]["peak"] for i in range(3)], weights=wk_pk))
    quotes.append({"months": q_months, "peak": round(q_peak, 2),
                   "offpeak": round(np.mean([quotes[i + 1]["offpeak"] for i in range(3)]), 2)})

    blocks = bootstrap_blocks(quotes, months)
    curve = shape_to_hourly(blocks, raw_shape, months)
    return {
        "months": months,
        "blocks": blocks,
        "curve": curve,
        "shape_profile": prof,
        "reaggregation_ok": verify_reaggregation(curve, blocks, months),
        "level_source": "illustrative strip (anchored to recent ERCOT level) — swap in CME futures",
        "shape_source": "real ERCOT hour-of-day profile",
    }


if __name__ == "__main__":
    r = build_forward_curve("data")
    print("forward curve months:", r["months"])
    print("re-aggregation exact?:", r["reaggregation_ok"], "\n")
    print(f"{'month':<9}{'peak $':>9}{'offpk $':>9}")
    for m in r["months"]:
        b = r["blocks"][m]
        print(f"{m:<9}{b['peak']:>9.2f}{b['offpeak']:>9.2f}")
    c = r["curve"]
    print(f"\nhourly curve: {len(c)} hours, {c.index.min()} -> {c.index.max()}")
    print(f"curve range: ${c.min():.1f} - ${c.max():.1f}/MWh")
