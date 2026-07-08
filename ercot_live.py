"""
ercot_live.py  —  the live-data seam (now with a real gridstatus puller).

Order of preference for data:
  1. LIVE pull via the `gridstatus` library (real ERCOT real-time SPP + AS MCPCs)
  2. Cached ERCOT CSVs that VoltStream already pulled (always works offline)

Live pulling is ON by default. To force cached-only (e.g. no internet), set:
      ERCOT_LIVE=0
Everything is wrapped so that ANY failure in the live path falls back cleanly to
the cached CSVs — the dashboard never breaks because a pull failed.

What "live" means here, honestly: fresh real ERCOT prices feeding a planning
model that recomputes on demand. It is NOT ERCOT's 5-minute SCED engine.
"""
import os
import time
import pandas as pd

SETTLEMENT_POINT = os.environ.get("ERCOT_SP", "HB_HOUSTON")
LIVE_ON = os.environ.get("ERCOT_LIVE", "1") != "0"
TTL = float(os.environ.get("ERCOT_LIVE_TTL", "300"))  # seconds between live pulls

# canonical AS names must match cooptimize.DEFAULT_AS
AS_CANON = ["RegUp", "RegDown", "RRS", "ECRS", "NonSpin"]
_AS_MATCH = {
    "RegUp":   lambda c: "regulation up" in c or c.strip() in ("regup", "regup mcpc"),
    "RegDown": lambda c: "regulation down" in c or "regdn" in c or "regdown" in c,
    "RRS":     lambda c: "responsive" in c or c.strip().startswith("rrs"),
    "ECRS":    lambda c: "contingency" in c or "ecrs" in c,
    "NonSpin": lambda c: "non-spin" in c or "non spin" in c or "nspin" in c or "nonspin" in c,
}

_cache = {"energy": (0.0, None), "as": (0.0, None), "src": "cached ERCOT CSVs (VoltStream pull)"}


def _pull_energy_gridstatus() -> pd.Series:
    """Real-time 15-min settlement-point price for the Houston hub, $/MWh."""
    from gridstatus import Ercot
    df = Ercot().get_spp(date="today", market="REAL_TIME_15_MIN", location_type="Trading Hub")
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    loc = cols.get("location", "Location")
    spp = cols.get("spp", cols.get("price", "SPP"))
    tcol = cols.get("interval start", cols.get("time", "Time"))
    sub = df[df[loc].astype(str).str.upper() == SETTLEMENT_POINT.upper()].copy()
    if sub.empty:
        raise RuntimeError(f"{SETTLEMENT_POINT} not in live SPP results")
    s = pd.Series(sub[spp].values, index=pd.to_datetime(sub[tcol].values)).sort_index()
    s.name = SETTLEMENT_POINT
    return s


def _pull_as_gridstatus(index) -> dict:
    """Real ERCOT AS clearing prices (MCPC), $/MW, aligned onto `index`."""
    from gridstatus import Ercot
    df = Ercot().get_as_prices(date="today")
    tcol = next((c for c in df.columns if c.lower() in ("interval start", "time")), df.columns[0])
    t = pd.to_datetime(df[tcol].values)
    out = {}
    for canon in AS_CANON:
        match = next((c for c in df.columns if _AS_MATCH[canon](c.lower())), None)
        if match is None:
            return {}  # incomplete -> signal caller to use synthetic
        ser = pd.Series(pd.to_numeric(df[match], errors="coerce").values, index=t).sort_index()
        # align hourly AS onto the (15-min) energy index by forward fill
        out[canon] = ser.reindex(pd.Index(index).union(ser.index)).ffill().reindex(index).bfill().values
    return out


def get_prices() -> pd.Series:
    """Clean 15-min price Series — rolling store (real, growing) first, then a single-day
    live pull, then cached CSVs. ERCOT_LIVE=0 forces the cached-CSV path unchanged."""
    from ercot_data import load_prices
    if LIVE_ON:
        ts, val = _cache["energy"]
        if val is not None and time.time() - ts < TTL:
            return val
        # 1. rolling price store — a real, continuous window over the last ~30 days.
        #    fetch_missing=False so a request never blocks on backfill (pre-warm populates it).
        try:
            import price_store
            # include_today=False: the archive store covers through yesterday (fresh enough for
            # the forecast, which targets the last COMPLETE day). Skipping today avoids a ~46s
            # gridstatus scrape on the landing endpoint. DART provides true intraday data separately.
            s, meta = price_store.get_prices_rolling(SETTLEMENT_POINT, days=30, fetch_missing=False,
                                                     include_today=False, backfill_if_thin=True)
            if s is not None and len(s) > 0:
                _cache["energy"] = (time.time(), s)
                _cache["src"] = meta["source"]
                print(f"[ercot_live] rolling store OK — {meta['points']} pts, "
                      f"{meta['days_cached']} cached days, latest ${float(s.iloc[-1]):.1f}/MWh")
                return s
        except Exception as e:
            print(f"[ercot_live] rolling store unavailable ({e}); trying single-day live pull")
        # 2. existing single-day live pull
        try:
            s = _pull_energy_gridstatus()
            if s is not None and len(s) > 0:
                _cache["energy"] = (time.time(), s)
                _cache["src"] = "LIVE ERCOT (gridstatus real-time SPP)"
                print(f"[ercot_live] live energy pull OK — {len(s)} pts, latest ${float(s.iloc[-1]):.1f}/MWh")
                return s
        except Exception as e:
            print(f"[ercot_live] live energy pull failed ({e}); using cached CSVs")
    # 3. cached CSVs (always works; the only path when ERCOT_LIVE=0)
    _cache["src"] = "cached ERCOT CSVs (VoltStream pull)"
    return load_prices(os.environ.get("ERCOT_DATA_DIR", "data"))


def get_as_prices(index):
    """Real AS MCPCs aligned to `index`, or None if unavailable (caller uses synthetic)."""
    if not LIVE_ON:
        return None
    ts, val = _cache["as"]
    if val is not None and time.time() - ts < TTL:
        return val
    try:
        d = _pull_as_gridstatus(index)
        if d and len(d) == len(AS_CANON):
            _cache["as"] = (time.time(), d)
            print(f"[ercot_live] live AS pull OK — real MCPCs for {', '.join(d.keys())}")
            return d
    except Exception as e:
        print(f"[ercot_live] live AS pull failed ({e}); using synthetic AS prices")
    return None


def data_source() -> str:
    return _cache["src"]
