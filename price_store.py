"""
price_store.py  —  the rolling price store (Phase 1 of live data).

Purpose: every engine except DART still runs on static May CSVs. This module gives the
platform a price memory that GROWS: per-day raw ERCOT real-time frames cached on disk,
assembled on demand into a continuous 15-min series per trading hub. Once the store holds
a few weeks, the forecaster/Bolt/co-opt/VPP/RT/risk all run on CURRENT prices and the
ERCOT_LIVE=0 crutch can retire.

Design decisions (deliberate):
  * SHARES the DART panel's cache. dart_engine already saves complete past days to
    dart_cache/REAL_TIME_15_MIN_{YYYY-MM-DD}.pkl — same files, same naming. One cache,
    two consumers, ERCOT is never fetched twice for the same day.
  * Complete past days are immutable -> cached forever. Today is always fetched fresh
    (it is still filling) and never written to the cache.
  * No synthetic anything. If the store has too little history it says so, and callers
    fall back to whatever they used before.

Backfill honesty: first-ever ensure_days(30) fetches each missing day live at roughly a
minute per day (gridstatus scrapes per-interval documents), so a 30-day backfill is a one-
time ~20-30 min run. After that, maintenance is one fetch per day.
"""
import os
import numpy as np
import pandas as pd

CACHE_DIR = os.environ.get("PRICE_CACHE_DIR", "dart_cache")
MARKET = "REAL_TIME_15_MIN"
HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]


def _path(day: str) -> str:
    return os.path.join(CACHE_DIR, f"{MARKET}_{day}.pkl")


# ----------------------- pure assembly core (fixture-testable) -----------------------
def _frame_to_series(df: pd.DataFrame, hub: str) -> pd.Series:
    """One raw gridstatus SPP frame -> 15-min price series for one hub."""
    tcol = next((c for c in ("Interval Start", "Time") if c in df.columns), df.columns[0])
    d = df[df["Location"].astype(str).str.upper() == hub.upper()].copy()
    if d.empty:
        return pd.Series(dtype=float)
    ts = pd.to_datetime(d[tcol])
    try:
        ts = ts.dt.tz_localize(None)
    except TypeError:
        pass
    s = pd.Series(pd.to_numeric(d["SPP"], errors="coerce").values, index=ts)
    return s.dropna()


def assemble(frames, hub: str) -> pd.Series:
    """Many raw day-frames -> one continuous, sorted, de-duplicated 15-min series."""
    parts = [_frame_to_series(f, hub) for f in frames]
    parts = [p for p in parts if len(p)]
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts).sort_index(kind="stable")   # stable: preserves load order among equal timestamps
    s = s[~s.index.duplicated(keep="last")]          # -> later-loaded frame deterministically wins
    s.name = f"{hub}_rt_spp"
    return s


# ----------------------- disk + live plumbing -----------------------
def cached_days():
    if not os.path.isdir(CACHE_DIR):
        return []
    out = []
    for f in sorted(os.listdir(CACHE_DIR)):
        if f.startswith(MARKET + "_") and f.endswith(".pkl"):
            out.append(f[len(MARKET) + 1:-4])
    return out


def ensure_days(n_days: int = 30, fetch_missing: bool = True, verbose: bool = True):
    """Make sure the last n complete days are cached. Returns (have, fetched, missing)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = pd.Timestamp.now().normalize()
    want = [(today - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(n_days, 0, -1)]
    have, fetched, missing = [], [], []
    iso = None
    for day in want:
        if os.path.exists(_path(day)):
            have.append(day)
            continue
        if not fetch_missing:
            missing.append(day)
            continue
        try:
            if iso is None:
                import gridstatus
                iso = gridstatus.Ercot()
            df = iso.get_spp(date=pd.Timestamp(day), market=MARKET, location_type="Trading Hub")
            df.to_pickle(_path(day))
            fetched.append(day)
            if verbose:
                print(f"price_store: fetched + cached {day} ({len(df)} rows)")
        except Exception as e:
            missing.append(day)
            if verbose:
                print(f"price_store: could not fetch {day} ({e})")
    return have + fetched, fetched, missing


def _today_frame():
    """Today's partial day, always fetched fresh, never cached."""
    import gridstatus
    iso = gridstatus.Ercot()
    frames = []
    for date in (pd.Timestamp.now().normalize(), "latest"):
        try:
            frames.append(iso.get_spp(date=date, market=MARKET, location_type="Trading Hub"))
        except Exception:
            pass
    return frames


def get_prices_rolling(hub: str = "HB_HOUSTON", days: int = 30, include_today: bool = True,
                       fetch_missing: bool = True, min_points: int = 96 * 3):
    """The store's main product: a continuous 15-min series over the rolling window.

    Raises RuntimeError (honestly) if the assembled history is too thin — callers keep
    their existing fallback. Returns (series, meta)."""
    have, fetched, missing = ensure_days(days, fetch_missing=fetch_missing)
    frames = []
    for day in have:
        try:
            frames.append(pd.read_pickle(_path(day)))
        except Exception:
            missing.append(day)
    if include_today:
        try:
            frames += _today_frame()
        except Exception:
            pass
    s = assemble(frames, hub)
    if len(s) < min_points:
        raise RuntimeError(f"rolling store too thin: {len(s)} pts < {min_points} "
                           f"({len(have)} cached days, {len(missing)} missing)")
    meta = {"hub": hub, "days_cached": len(have), "days_fetched_now": len(fetched),
            "days_missing": len(missing), "points": len(s),
            "start": str(s.index.min()), "end": str(s.index.max()),
            "source": f"rolling store ({len(have)} cached days + today, live ERCOT via gridstatus)"}
    return s, meta


# ----------------------- fixture self-test -----------------------
if __name__ == "__main__":
    import tempfile
    # Build synthetic gridstatus-shaped day frames (clearly a FIXTURE: verifies assembly, not the market)
    rng = np.random.default_rng(11)
    frames = []
    for d in ("2026-06-30", "2026-07-01", "2026-07-02"):
        idx = pd.date_range(d, periods=96, freq="15min")
        rows = []
        for hub in HUBS + ["LZ_SOUTH"]:                      # includes a non-hub row to be filtered
            base = 30 + (0 if hub != "HB_WEST" else -5)
            for t, v in zip(idx, base + rng.normal(0, 4, 96)):
                rows.append({"Interval Start": t, "Location": hub, "SPP": v, "Market": MARKET})
        frames.append(pd.DataFrame(rows))
    # overlap: repeat day 2 with shifted values -> dedup must keep exactly 96 pts for that day
    dup = frames[1].copy(); dup["SPP"] = dup["SPP"] + 100.0
    s = assemble(frames + [dup], "HB_HOUSTON")
    assert len(s) == 3 * 96, f"expected 288 pts, got {len(s)}"
    step = s.index.to_series().diff().dropna().median()
    assert step == pd.Timedelta("15min"), f"expected 15-min cadence, got {step}"
    assert s.index.is_monotonic_increasing and not s.index.duplicated().any()
    day2 = s[s.index.normalize() == pd.Timestamp("2026-07-01")]
    assert (day2 > 80).all(), "dedup should keep the LAST frame's values (the +100 dup)"
    w = assemble(frames, "HB_WEST")
    assert w.mean() < assemble(frames, "HB_NORTH").mean(), "hub filtering broken"

    # disk round-trip through the real cache path machinery
    with tempfile.TemporaryDirectory() as td:
        globals()["CACHE_DIR"] = td
        for f, d in zip(frames, ("2026-06-30", "2026-07-01", "2026-07-02")):
            f.to_pickle(_path(d))
        assert cached_days() == ["2026-06-30", "2026-07-01", "2026-07-02"]
        have, fetched, missing = ensure_days(3, fetch_missing=False)
        # (relative to the real today these fixture days count as missing; the call must not crash)
    print("fixture self-test PASSED")
    print(f"  assembled {len(s)} pts @ 15-min, dedup keeps last, hub filter OK, cache listing OK")
    print("  (fixture verifies ASSEMBLY; live fetch + backfill verified on the Mac)")
