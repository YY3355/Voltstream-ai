"""desk_data.py — daily bucket-average price series from VoltStream's REAL archive, for the
structuring desk. RT from price_store's rolling store (deep as the cache reaches); DA from the
dart_cache DAY_AHEAD_HOURLY pickles. Nothing synthetic, nothing smoothed.

Bucket definition (declared, not assumed): peak = hours-ending 07-22 (clock 06:00-21:59), ALL days;
offpeak = the rest. Depth is whatever the archive holds — callers must report n_obs honestly.
"""
from __future__ import annotations
import glob
import os
import numpy as np
import pandas as pd

PEAK_CLOCK_HOURS = list(range(6, 22))  # clock hours 06..21 == hours-ending 07..22
BUCKET_DEF = "peak = hours-ending 07-22 (clock 06:00-21:59), all days; offpeak = the rest"
DA_GLOB = os.path.join(os.environ.get("PRICE_CACHE_DIR", "dart_cache"), "DAY_AHEAD_HOURLY_*.pkl")


def _to_naive(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize(None) if idx.tz is not None else idx


def _daily_bucket(series: pd.Series, bucket: str) -> pd.Series:
    """Collapse a sub-daily price series to a daily bucket-average series (date-indexed)."""
    s = pd.Series(series.dropna().values, index=_to_naive(series.dropna().index)).sort_index()
    onpeak = np.isin(s.index.hour, PEAK_CLOCK_HOURS)
    mask = onpeak if bucket == "peak" else ~onpeak
    sub = s[mask]
    if sub.empty:
        return pd.Series(dtype=float)
    daily = sub.groupby(sub.index.normalize()).mean()
    daily.index = pd.DatetimeIndex(daily.index)
    daily.name = None
    return daily.sort_index()


def _da_hourly(hub: str) -> pd.Series:
    """Assemble the archived DA hourly series for one hub from the dart_cache DA pickles."""
    parts = []
    for f in sorted(glob.glob(DA_GLOB)):
        try:
            df = pd.read_pickle(f)
        except Exception:
            continue
        d = df[df["Location"].astype(str).str.upper() == hub.upper()]
        if d.empty:
            continue
        ts = _to_naive(pd.to_datetime(d["Interval Start"]))
        parts.append(pd.Series(pd.to_numeric(d["SPP"], errors="coerce").values, index=ts))
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")].dropna()


def daily_bucket(hub: str, market: str, bucket: str, days: int = 400):
    """(daily bucket-average series, meta) for hub × market(da|rt) × bucket(peak|offpeak).
    RT uses only cached archive days (no network). Raises ValueError on bad market/bucket."""
    hub = (hub or "HB_HOUSTON").upper()
    market = (market or "rt").lower()
    bucket = (bucket or "peak").lower()
    if market not in ("da", "rt"):
        raise ValueError(f"market must be da|rt, got {market!r}")
    if bucket not in ("peak", "offpeak"):
        raise ValueError(f"bucket must be peak|offpeak, got {bucket!r}")

    if market == "rt":
        import price_store
        raw, pmeta = price_store.get_prices_rolling(hub, days=days, include_today=False,
                                                    fetch_missing=False)
        source = pmeta.get("source", "price_store rolling (RT 15-min, real ERCOT)")
    else:
        raw = _da_hourly(hub)
        source = f"dart_cache DA-hourly pickles ({DA_GLOB})"

    daily = _daily_bucket(raw, bucket)
    meta = {"hub": hub, "market": market, "bucket": bucket, "bucket_def": BUCKET_DEF,
            "n_days": int(len(daily)), "source": source,
            "start": str(daily.index[0].date()) if len(daily) else None,
            "end": str(daily.index[-1].date()) if len(daily) else None}
    return daily, meta
