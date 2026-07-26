"""build_snapshots.py — rebuild clim_result.json + vol_result.json against the MERGED deep archive.

RT (15-min) per hub = decade/ (HB_HOUSTON, 2018+) ∪ data/ CSVs (4 hubs, ~1yr) ∪ rolling store (recent).
DA (hourly) per hub = dam_decade/ bundles (4 hubs, 2018+) ∪ dart_cache DA (recent).
Climatology = DA ∩ hourly-RT pairs by (month,hour). Vol = realized_vol 20/60/250 + cone on daily bucket.

Per-hub depth is honest and varies (HB_HOUSTON deepest — it has the RT decade). Prints the numbers.
Writes NOTHING into journal/. Run: conda run -n volt python scripts/build_snapshots.py
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import desk_data
import vol_engine as ve
from desk_climatology import build_climatology

HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]


def _naive(s):
    return pd.Series(s.values, index=desk_data._to_naive(s.index))


def _data_rt_15min(hub):
    parts = []
    for f in sorted(glob.glob("data/ercot_api_*.csv")):
        day = os.path.basename(f).replace("ercot_api_", "").replace(".csv", "")
        d = pd.read_csv(f)
        if hub not in d.columns:
            continue
        ts = pd.to_datetime(day) + pd.to_timedelta(d["hour"].astype(int), "h") + pd.to_timedelta(d["minute"].astype(int), "m")
        parts.append(pd.Series(pd.to_numeric(d[hub], errors="coerce").values, index=ts))
    return pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)


def merged_rt_15min(hub):
    parts = []
    for f in sorted(glob.glob("data_archive/decade/*.pkl")):     # HB_HOUSTON RT decade
        s = pd.read_pickle(f)
        if getattr(s, "name", "") and hub.upper() in str(s.name).upper():
            parts.append(_naive(s))
    parts.append(_data_rt_15min(hub))                            # data/ CSVs (4 hubs, ~1yr)
    try:
        import price_store
        rt15, _ = price_store.get_prices_rolling(hub, days=400, include_today=False, fetch_missing=False)
        parts.append(_naive(rt15))                               # recent rolling store
    except Exception:
        pass
    s = pd.concat([p for p in parts if len(p)]).sort_index()
    return s[~s.index.duplicated(keep="last")].dropna()


def merged_da_hourly(hub):
    parts = []
    for f in sorted(glob.glob("data_archive/dam_decade/*.pkl")):  # DA decade (4 hubs)
        df = pd.read_pickle(f)
        if hub in df.columns:
            parts.append(_naive(df[hub]))
    da = desk_data._da_hourly(hub)                                # dart_cache recent
    if len(da):
        parts.append(da)
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")].dropna()


def main():
    clim_hubs, vol_hubs = {}, {}
    print("hub          RT_days   DA_days   pair_hrs  clim_cells_ok  vol_cone_windows(n250)")
    for hub in HUBS:
        rt = merged_rt_15min(hub)
        da = merged_da_hourly(hub)
        rt_h = rt.resample("h").mean()
        idx = da.index.intersection(rt_h.index)
        pdf = pd.DataFrame({"ts": idx, "da": da.reindex(idx).values, "rt": rt_h.reindex(idx).values}).dropna()
        clim = build_climatology(pdf, label=hub)
        n_ok = sum(1 for c in clim["cells"].values() if not c.get("insufficient"))
        clim_hubs[hub] = clim
        # vol per market (deep RT + deep DA) x bucket
        markets = {}
        for market, series in (("rt", rt), ("da", da)):
            buckets = {}
            for bucket in ("peak", "offpeak"):
                db = desk_data._daily_bucket(series, bucket)
                if len(db) < 3:
                    buckets[bucket] = {"n_days": int(len(db)), "error": "too thin"}
                    continue
                buckets[bucket] = {
                    "n_days": int(len(db)),
                    "windows": [ve.realized_vol(db, window_days=w, label=f"{hub} {market} {bucket}").to_dict()
                                for w in (20, 60, 250)],
                    "cone": ve.vol_cone(db, windows=(20, 60, 120, 250, 500), label=f"{hub} {market} {bucket}"),
                    "start": str(db.index[0].date()), "end": str(db.index[-1].date()),
                    "n_excluded_nonpos": ve.realized_vol(db, label="").n_excluded_nonpos,
                }
            markets[market] = buckets
        n250 = next((c["n_samples"] for c in ve.vol_cone(desk_data._daily_bucket(rt, "peak"),
                     windows=(250,))["windows"] if c["window_days"] == 250), 0)
        cone = ve.vol_cone(desk_data._daily_bucket(rt, "peak"), windows=(20, 60, 120, 250, 500))
        vol_hubs[hub] = {"hub": hub, "markets": markets,
                         "label": "realized, not implied — no option quotes available",
                         "source": "merged: RT decade + data/ + store (RT); DAM bundle decade (DA)"}
        print(f"{hub:<12} {rt.index.normalize().nunique():>7}  {da.index.normalize().nunique():>7}  "
              f"{len(pdf):>8}  {n_ok:>13}  {[c['window_days'] for c in cone['windows']]} (n250={n250})")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    spans = [c["date_range"] for c in clim_hubs.values() if c["n_hours_total"]]
    clim_out = {
        "kind": "climatology_baseline",
        "coverage_note": ("Empirical (month,hour) P(RT>DA) and DART quantiles from archived ERCOT "
                          "settlements: DA from DAM monthly bundles (NP4-190-CD), RT from the SPP decade "
                          "cache + archive. Per-hub coverage below; cells with n<30 render '—'. Baseline "
                          "the eval-harnessed model must beat."),
        "pair_coverage": {"start": min(r[0] for r in spans), "end": max(r[1] for r in spans)} if spans else {},
        "totals": {"cells_sufficient": sum(1 for h in clim_hubs.values() for c in h["cells"].values() if not c.get("insufficient")),
                   "cells": sum(len(h["cells"]) for h in clim_hubs.values())},
        "hubs": clim_hubs, "built_at": now,
        "fly_caveat": "committed snapshot (like decade_result.json); deep caches are gitignored, deployed app reads this.",
    }
    json.dump(clim_out, open("clim_result.json", "w"), indent=1)
    vol_out = {"kind": "realized_vol_snapshot", "label": "realized, not implied — no option quotes available",
               "bucket_def": desk_data.BUCKET_DEF, "hubs": vol_hubs, "built_at": now,
               "note": "committed vol snapshot from the merged deep archive; /api/vol prefers this over the thin live store."}
    json.dump(vol_out, open("vol_result.json", "w"), indent=1)
    print(f"\nwrote clim_result.json ({clim_out['totals']['cells_sufficient']}/{clim_out['totals']['cells']} cells sufficient) "
          f"+ vol_result.json | pair span {clim_out['pair_coverage']}")


if __name__ == "__main__":
    main()
