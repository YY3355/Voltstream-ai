"""backfill_dam.py — backfill DAM Settlement Point Prices (NP4-190-CD) monthly bundles into a
per-year DA hourly cache (data_archive/dam_decade/{year}.pkl), the DA analog of the RT decade cache.
Parses the DAM hourly schema (DeliveryDate,HourEnding,SettlementPoint,SettlementPointPrice,DSTFlag).

Usage: conda run -n volt python scripts/backfill_dam.py <from_YYYY-MM> [<to_YYYY-MM>]
"""
import io
import os
import sys
import time
import zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
import pandas as pd
import ercot_archiver as A

HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]
OUT_DIR = os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "dam_decade")
EMIL = "NP4-190-CD"


def dam_bundle_to_hub_series(zip_bytes, hubs):
    """One DAM monthly bundle -> {hub: hourly DA Series}. Timestamp = DeliveryDate + (HourEnding-1)h."""
    keys = {h: f",{h.upper()}," for h in hubs}
    acc = {h: ([], []) for h in hubs}
    outer = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in outer.namelist():
        try:
            izf = zipfile.ZipFile(io.BytesIO(outer.read(name)))
            txt = izf.read(izf.namelist()[0]).decode("utf-8", "ignore")
        except Exception:
            continue
        for line in txt.splitlines():
            for h, key in keys.items():
                if key in line:
                    f = line.split(",")
                    try:
                        he = int(f[1].split(":")[0])
                        t = pd.Timestamp(f[0]) + pd.Timedelta(hours=he - 1)
                        acc[h][0].append(t); acc[h][1].append(float(f[3]))
                    except Exception:
                        pass
                    break
    out = {}
    for h in hubs:
        s = pd.Series(acc[h][1], index=pd.DatetimeIndex(acc[h][0])).sort_index()
        out[h] = s[~s.index.duplicated(keep="last")]
    return out


def backfill(from_month, to_month=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    bundles = A.list_bundles(EMIL)
    to_month = to_month or bundles[-1]["date"][:7]
    want = [b for b in bundles if from_month <= b["name"][-7:] <= to_month]
    print(f"DAM backfill {from_month}..{to_month}: {len(want)} bundles", flush=True)
    by_year = {}
    for i, b in enumerate(want, 1):
        t0 = time.time()
        try:
            series = dam_bundle_to_hub_series(A._get(b["href"], timeout=180).content, HUBS)
        except Exception as e:
            print(f"  [{i}/{len(want)}] {b['name']} FAILED ({e})", flush=True)
            continue
        n = len(series["HB_HOUSTON"])
        for h, s in series.items():
            for yr, g in s.groupby(s.index.year):
                by_year.setdefault(int(yr), {}).setdefault(h, []).append(g)
        print(f"  [{i}/{len(want)}] {b['name']} -> HB_HOUSTON {n} hrs ({time.time()-t0:.1f}s)", flush=True)
    # write per-year DataFrames (cols = hubs)
    for yr, hubmap in by_year.items():
        cols = {}
        for h, parts in hubmap.items():
            s = pd.concat(parts).sort_index()
            cols[h] = s[~s.index.duplicated(keep="last")]
        df = pd.DataFrame(cols).sort_index()
        df.to_pickle(os.path.join(OUT_DIR, f"{yr}.pkl"))
        print(f"  wrote {yr}.pkl: {len(df)} hrs, {str(df.index.min())[:10]}..{str(df.index.max())[:10]}", flush=True)
    print("DAM backfill done.", flush=True)


if __name__ == "__main__":
    backfill(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
