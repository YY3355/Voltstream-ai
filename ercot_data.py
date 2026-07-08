"""
ercot_data.py  —  data pipeline for the real ERCOT prices pulled by VoltStream.

The raw files are messy in three ways this loader handles:
  1. interval-ending formats differ ('15','100' vs '0015','0100')
  2. one file (may2) bundles 7 forecast vintages under a 'source' column
  3. one file is missing the load-zone columns
We standardize to a single clean, de-duplicated, time-indexed price series
for the Houston hub (HB_HOUSTON, present in every file).
"""
import glob
import os
import pandas as pd

TARGET = "HB_HOUSTON"


def _interval_to_minutes(x) -> int:
    """'15'->15, '100'->60, '0015'->15, '2400'->1440."""
    s = str(int(str(x).strip())).zfill(4)
    return int(s[:-2]) * 60 + int(s[-2:])


def _load_one(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "source" in df.columns:                 # may2: keep the realized ('Today') vintage only
        df = df[df["source"] == "Today"].copy()
    if TARGET not in df.columns:
        return pd.DataFrame(columns=["ts", TARGET])
    mins = df["Interval Ending"].map(_interval_to_minutes)
    ts = pd.to_datetime(df["Oper Day"], format="%m/%d/%Y") + pd.to_timedelta(mins, unit="m")
    return pd.DataFrame({"ts": ts, TARGET: df[TARGET].values})


def load_prices(data_dir: str = "data") -> pd.Series:
    """Return a clean, sorted, de-duplicated 15-min HB_HOUSTON price series ($/MWh).

    Prefers the rolling price store (real, recent, complete days) when enabled, so the
    engines that call this directly (rt / risk / qse / forward-curve) run on current prices
    without being touched. Gated on PRICE_STORE!="0" AND ERCOT_LIVE!="0" — so ERCOT_LIVE=0
    stays a clean fully-offline switch that falls through to the cached CSVs unchanged.
    include_today=False keeps only complete 96-pt days for the engines' per-day logic."""
    if os.environ.get("PRICE_STORE", "1") != "0" and os.environ.get("ERCOT_LIVE", "1") != "0":
        try:
            import price_store
            s, _meta = price_store.get_prices_rolling(TARGET, days=30, include_today=False,
                                                      fetch_missing=False, backfill_if_thin=True)
            if s is not None and len(s) > 0:
                return s.astype(float)
        except Exception:
            pass  # store thin/unavailable -> fall through to the cached CSVs
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    frames = [f for f in (_load_one(f) for f in files) if len(f)]
    if not frames:                                          # no CSVs (e.g. fresh clone) and store thin
        return pd.Series(dtype=float, name=TARGET)
    s = (
        pd.concat(frames)
        .dropna()
        .drop_duplicates("ts")
        .sort_values("ts")
        .set_index("ts")[TARGET]
        .astype(float)
    )
    return s


if __name__ == "__main__":
    s = load_prices()
    print(f"{len(s)} intervals  |  {s.index.min()} -> {s.index.max()}")
    print(f"price $/MWh  min/median/mean/max: {s.min():.1f} / {s.median():.1f} / {s.mean():.1f} / {s.max():.1f}")
