"""
dart_engine.py  —  DART spreads + congestion-proxy monitor (live ERCOT data).

DART = Day-Ahead minus Real-Time. You commit at the day-ahead (DA) price and the same
hour settles at the real-time (RT) price; the spread between them is one of the most
traded relationships in power. A desk watches: is DA systematically rich or cheap, by
hub, by hour of day, and how volatile is the spread?

CONGESTION PROXY: hub-to-hub basis (e.g. West vs North). Persistent basis exists because
transmission constraints separate regions — West Texas wind congestion is the classic.
This is an HONEST PROXY at hub granularity: real congestion work is nodal (DCOPF, binding
constraints, shadow prices), which this deliberately does not claim to do.

Data: live via gridstatus (DAY_AHEAD_HOURLY + REAL_TIME_15_MIN, Trading Hubs), the same
call shape as ercot_live.py. There is NO synthetic fallback for DA prices — if the live
pull fails the module says so honestly rather than inventing a day-ahead market.
"""
import os
import logging
import threading
import numpy as np
import pandas as pd

HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]
_cache = {"data": None, "ts": 0.0}
_lock = threading.Lock()               # serialize fetches so a pre-warm + a page load don't double-scrape
TTL = 1800  # refetch at most every 30 min

log = logging.getLogger(__name__)
# on-disk cache of per-day raw SPP pulls, so a restart doesn't re-scrape complete past days
# (RT 15-min is ~55s/day via gridstatus; DA hourly ~2.5s/day). Only COMPLETE past days are
# cached — today is still filling and the "latest" pull is always fresh.
CACHE_DIR = os.environ.get("DART_CACHE_DIR", os.path.join(os.path.dirname(__file__), "dart_cache"))


# ------------------------ pure compute core (fixture-testable) ------------------------
def _hourly_by_hub(df, value_col="SPP"):
    """gridstatus SPP frame -> hourly mean price per hub (DataFrame indexed by hour, cols=hubs)."""
    tcol = next((c for c in ("Interval Start", "Time") if c in df.columns), df.columns[0])
    d = df.copy()
    d["ts"] = pd.to_datetime(d[tcol]).dt.tz_localize(None)
    d["hub"] = d["Location"].astype(str).str.upper()
    d = d[d["hub"].isin(HUBS)]
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce")
    out = (d.set_index("ts").groupby("hub")[value_col]
             .resample("1h").mean().unstack(0))
    return out.dropna(how="all")


def compute_dart(da_hourly: pd.DataFrame, rt_hourly: pd.DataFrame):
    """Join DA and RT hourly-by-hub frames and compute the DART book. Pure function."""
    hubs = [h for h in HUBS if h in da_hourly.columns and h in rt_hourly.columns]
    idx = da_hourly.index.intersection(rt_hourly.index)
    da, rt = da_hourly.loc[idx, hubs], rt_hourly.loc[idx, hubs]
    dart = da - rt                                   # positive = DA settled rich vs RT

    stats = {}
    for h in hubs:
        s = dart[h].dropna()
        if not len(s):
            continue
        stats[h] = {
            "mean": round(float(s.mean()), 2),
            "std": round(float(s.std()), 2),
            "hit_rate_pct": round(100 * float((s > 0).mean()), 1),   # how often DA rich
            "n_hours": int(len(s)),
            "cum_1mw": round(float(s.sum()), 2),     # settlement of a constant 1 MW sell-DA/buy-RT
        }

    # hour-of-day bias (the classic DART clock), Houston as the reference hub
    ref = "HB_HOUSTON" if "HB_HOUSTON" in dart.columns else hubs[0]
    hod = dart[ref].groupby(dart.index.hour).mean()
    hod_profile = [{"hour": int(h), "dart": round(float(v), 2)} for h, v in hod.items()]

    # congestion proxy: hub basis vs HB_NORTH (the conventional reference)
    basis = {}
    if "HB_NORTH" in rt.columns:
        for h in hubs:
            if h == "HB_NORTH":
                continue
            b = (rt[h] - rt["HB_NORTH"]).dropna()
            if len(b):
                basis[h.replace("HB_", "") + "-NORTH"] = {
                    "mean": round(float(b.mean()), 2),
                    "std": round(float(b.std()), 2),
                    "last": round(float(b.iloc[-1]), 2),
                    "max_abs": round(float(b.abs().max()), 2),
                }

    # chart payloads: last ~72h of DA vs RT (ref hub) + dart series, and RT West-North basis
    tail = dart.index[-min(len(dart), 72):]
    series = {
        "ts": [t.strftime("%m-%d %H:%M") for t in tail],
        "da": [round(float(x), 2) for x in da.loc[tail, ref]],
        "rt": [round(float(x), 2) for x in rt.loc[tail, ref]],
        "dart": [round(float(x), 2) for x in dart.loc[tail, ref]],
    }
    basis_series = None
    if "HB_WEST" in rt.columns and "HB_NORTH" in rt.columns:
        bs = (rt["HB_WEST"] - rt["HB_NORTH"]).loc[tail]
        basis_series = [round(float(x), 2) for x in bs]

    return {"hubs": hubs, "ref_hub": ref, "stats": stats, "hod_profile": hod_profile,
            "basis": basis, "series": series, "basis_series": basis_series,
            "window": {"start": str(idx.min()), "end": str(idx.max()), "hours": int(len(idx))}}


# ------------------------ live fetch (runs on the Mac, not sandbox) ------------------------
def _cache_path(market, day):
    return os.path.join(CACHE_DIR, f"{market}_{day.strftime('%Y-%m-%d')}.pkl")


def _get_spp_day(iso, market, day, use_cache):
    """One day of SPP for a market. Complete past days are read from / written to a disk
    cache (raw gridstatus frame, pickled) so restarts don't re-scrape them."""
    if use_cache:
        p = _cache_path(market, day)
        if os.path.exists(p):
            try:
                df = pd.read_pickle(p)
                log.info("dart_cache HIT  %s %s (%d rows)", market, day.date(), len(df))
                return df
            except Exception:
                log.info("dart_cache CORRUPT %s %s -> refetch", market, day.date())
    df = iso.get_spp(date=day, market=market, location_type="Trading Hub")
    if use_cache and df is not None and len(df):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            df.to_pickle(_cache_path(market, day))
            log.info("dart_cache MISS %s %s -> fetched + cached (%d rows)", market, day.date(), len(df))
        except Exception as e:
            log.info("dart_cache write failed %s %s: %r", market, day.date(), e)
    return df


def fetch_live(days=5):
    """Pull DA-hourly and RT-15min hub SPPs via gridstatus; mirrors ercot_live.py's call shape.

    Complete past days come from the disk cache when present; today (still filling) and the
    trailing "latest" RT pull are always fetched fresh."""
    import gridstatus
    iso = gridstatus.Ercot()
    today = pd.Timestamp.now().normalize()
    da_frames, rt_frames = [], []
    for k in range(days, -1, -1):
        day = today - pd.Timedelta(days=k)
        use_cache = k >= 1                      # only cache COMPLETE past days; today is still filling
        for market, bucket in (("DAY_AHEAD_HOURLY", da_frames), ("REAL_TIME_15_MIN", rt_frames)):
            try:
                bucket.append(_get_spp_day(iso, market, day, use_cache))
            except Exception:
                pass
    try:
        rt_frames.append(iso.get_spp(date="latest", market="REAL_TIME_15_MIN", location_type="Trading Hub"))
    except Exception:
        pass
    if not da_frames or not rt_frames:
        raise RuntimeError("live DA/RT pull returned nothing")
    da = _hourly_by_hub(pd.concat(da_frames, ignore_index=True))
    rt = _hourly_by_hub(pd.concat(rt_frames, ignore_index=True))
    return da, rt


def run_dart(days=5):
    """Top level with cache. Returns the DART book or an honest error (no synthetic DA)."""
    import time
    if _cache["data"] is not None and time.time() - _cache["ts"] < TTL:
        return _cache["data"]
    with _lock:
        # another caller (e.g. the startup pre-warm) may have populated the cache while we waited
        if _cache["data"] is not None and time.time() - _cache["ts"] < TTL:
            return _cache["data"]
        try:
            da, rt = fetch_live(days)
            result = compute_dart(da, rt)
            result["data_source"] = "LIVE ERCOT via gridstatus (DA hourly + RT 15-min, Trading Hubs)"
            _cache["data"] = result; _cache["ts"] = time.time()
            return result
        except Exception as e:
            return {"error": f"live DART pull unavailable ({e}). No synthetic fallback — "
                             f"a day-ahead market can't be honestly faked."}


# ------------------------ fixture self-test ------------------------
if __name__ == "__main__":
    # Synthetic FIXTURE (clearly labeled): verifies the math, not the market.
    rng = np.random.default_rng(3)
    hrs = pd.date_range("2026-06-25", periods=96, freq="1h")
    rows_da, rows_rt = [], []
    for h in HUBS:
        base = 30 + 6 * np.sin(np.arange(96) / 24 * 2 * np.pi)
        west_kick = -4.0 if h == "HB_WEST" else 0.0            # West basis (congestion-like)
        rt_price = base + west_kick + rng.normal(0, 5, 96)
        da_price = base + west_kick + 1.5 + rng.normal(0, 2, 96)   # DA rich by ~$1.5 on average
        for t, v in zip(hrs, da_price):
            rows_da.append({"Interval Start": t, "Location": h, "SPP": v})
        for t, v in zip(hrs, rt_price):
            rows_rt.append({"Interval Start": t, "Location": h, "SPP": v})
    da = _hourly_by_hub(pd.DataFrame(rows_da)); rt = _hourly_by_hub(pd.DataFrame(rows_rt))
    r = compute_dart(da, rt)
    hou = r["stats"]["HB_HOUSTON"]
    assert 0.5 < hou["mean"] < 2.5, f"DART mean off: {hou['mean']}"           # ~ +1.5 by construction
    assert hou["hit_rate_pct"] > 50, "DA-rich fixture should hit >50%"
    assert abs(r["basis"]["WEST-NORTH"]["mean"] + 4.0) < 1.0, "West basis should be ~ -$4"
    assert len(r["series"]["da"]) == len(r["series"]["rt"]) == len(r["series"]["ts"])
    print("fixture self-test PASSED")
    print(f"  Houston DART: mean ${hou['mean']}/MWh, hit rate {hou['hit_rate_pct']}%, "
          f"cum 1MW ${hou['cum_1mw']} over {hou['n_hours']}h")
    print(f"  West-North basis: mean ${r['basis']['WEST-NORTH']['mean']} (built as -$4)")
    print("  (fixture verifies the MATH; live data is verified on the Mac via /api/dart)")
