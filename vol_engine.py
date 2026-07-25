"""vol_engine.py — realized volatility from VoltStream's own price archive.

HONEST SCOPE (display these labels in the UI):
- This is REALIZED volatility measured from archived ERCOT settlement prices.
  It is NOT implied volatility. No power-option quotes are available to us,
  so no market vol surface exists here. Realized vol is an input estimate,
  not a market price of risk.
- Power prices can be negative (ERCOT wind hours). Lognormal (Black-76)
  conventions break on non-positive prices. We therefore report BOTH:
    * normal_vol  — Bachelier convention, $/MWh per sqrt(year), uses ALL days
    * log_vol     — lognormal convention, uses only strictly positive prices;
                    excluded-day count is reported, never hidden
- Every result carries provenance: source series, window, day counts, asof.

Input contract (matches price_store daily cache shape):
    a pandas Series indexed by date (datetime.date or Timestamp),
    values = daily average price for the bucket (e.g. DA peak avg, $/MWh).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

TRADING_DAYS = 365  # power settles every calendar day; declare, don't assume 252

@dataclass
class VolResult:
    label: str                # e.g. "HB_HOUSTON DA peak"
    window_days: int
    n_obs: int                # return observations actually used
    n_excluded_nonpos: int    # days dropped for log-vol (non-positive prices)
    normal_vol: float         # $/MWh per sqrt(yr), Bachelier convention, all days
    log_vol: float | None     # annualized lognormal vol; None if too few positive days
    mean_price: float
    start: str
    end: str
    convention_note: str
    asof: str

    def to_dict(self):
        return asdict(self)


def _clean(series: pd.Series) -> pd.Series:
    s = series.dropna().sort_index()
    if len(s) < 2:
        raise ValueError("need at least 2 observations")
    return s


def realized_vol(series: pd.Series, window_days: int | None = None,
                 label: str = "") -> VolResult:
    """Realized vol over the trailing window (or full series if None)."""
    s = _clean(series)
    if window_days is not None:
        s = s.iloc[-(window_days + 1):]  # +1: n prices -> n-1 returns
    # --- normal (Bachelier) vol: first differences, valid for any sign ---
    diffs = s.diff().dropna()
    normal_vol = float(diffs.std(ddof=1) * np.sqrt(TRADING_DAYS))
    # --- log vol: strictly positive consecutive pairs only ---
    pos = s > 0
    pair_ok = pos & pos.shift(1).fillna(False)
    n_excluded = int((~pos).sum())
    if pair_ok.sum() >= 20:  # refuse to report log vol on thin data
        lr = np.log(s[pair_ok] / s.shift(1)[pair_ok])
        log_vol = float(lr.std(ddof=1) * np.sqrt(TRADING_DAYS))
    else:
        log_vol = None
    return VolResult(
        label=label,
        window_days=window_days if window_days is not None else len(s) - 1,
        n_obs=len(diffs),
        n_excluded_nonpos=n_excluded,
        normal_vol=normal_vol,
        log_vol=log_vol,
        mean_price=float(s.mean()),
        start=str(s.index[0])[:10],
        end=str(s.index[-1])[:10],
        convention_note=("realized vol from archived settlements; NOT implied. "
                         f"annualization={TRADING_DAYS}d. log_vol excludes "
                         "non-positive prices (count shown)."),
        asof=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def vol_cone(series: pd.Series, windows=(20, 60, 120, 250, 500),
             label: str = "") -> dict:
    """Vol cone: for each window length, the distribution of trailing realized
    vols across history (min/25th/median/75th/max) plus the CURRENT value.
    All measured; nothing interpolated."""
    s = _clean(series)
    out = {"label": label, "windows": [], "convention": "normal ($/MWh/sqrt-yr)",
           "asof": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    diffs = s.diff().dropna()
    for w in windows:
        if len(diffs) < w + 5:
            continue
        roll = diffs.rolling(w).std(ddof=1).dropna() * np.sqrt(TRADING_DAYS)
        q = roll.quantile([0.0, 0.25, 0.5, 0.75, 1.0])
        out["windows"].append({
            "window_days": w, "n_samples": int(len(roll)),
            "min": float(q.iloc[0]), "p25": float(q.iloc[1]),
            "median": float(q.iloc[2]), "p75": float(q.iloc[3]),
            "max": float(q.iloc[4]), "current": float(roll.iloc[-1]),
        })
    return out
