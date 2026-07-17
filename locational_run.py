"""
locational_run.py  —  extract per-hub decade price series from the monthly ERCOT SPP bundles
and build the locational-revenue playback JSON for /api/locational.

The cached data_archive/decade/*.pkl hold only HB_HOUSTON, and backfill_decade_hub does not
cache the raw bundle zips — so this RE-DOWNLOADS the monthly bundles once and parses all four
trading hubs per download (network dominates; the parse is a fast string scan). Minutes of
compute; run once. Per-hub series are cached (gitignored) so re-runs skip the network.
"""
import io
import json
import os
import zipfile

import pandas as pd

import map_data
import locational_revenue as LR
from ercot_archiver import list_bundles, _get

ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "data_archive")
HUB_PKL_DIR = os.path.join(ARCHIVE_DIR, "locational")          # gitignored per-hub series cache
# small summary committed at repo root (ships in the image), like decade_result.json
RESULT_JSON = os.environ.get("LOCATIONAL_RESULT",
                             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "locational_result.json"))
HUBS = LR.HUBS
Y_LO, Y_HI = 2018, 2025


def bundle_to_hubs(zip_bytes, hubs):
    """Single-pass multi-hub parse of one monthly SPP bundle. Reuses the exact timestamp
    formula verified in ercot_archiver.bundle_to_hub_series (ts = DeliveryDate + (H-1)h +
    (I-1)*15min), but collects all requested hubs from one scan of each inner CSV."""
    keys = {h: f",{h.upper()}," for h in hubs}
    acc = {h: ([], []) for h in hubs}
    outer = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in outer.namelist():
        try:
            izf = zipfile.ZipFile(io.BytesIO(outer.read(name)))
            txt = izf.read(izf.namelist()[0]).decode("utf-8", "ignore")
        except Exception:
            continue
        seen = 0
        for line in txt.splitlines():
            for h, key in keys.items():
                if key in line:                                # DeliveryDate,H,I,HUB,HU,price,DST
                    f = line.split(",")
                    try:
                        ts = pd.Timestamp(f[0]) + pd.Timedelta(
                            minutes=(int(f[1]) - 1) * 60 + (int(f[2]) - 1) * 15)
                        acc[h][0].append(ts)
                        acc[h][1].append(float(f[5]))
                    except Exception:
                        pass
                    seen += 1
                    break
            if seen >= len(hubs):
                break
    out = {}
    for h, (ts, px) in acc.items():
        s = pd.Series(px, index=pd.DatetimeIndex(ts)).sort_index()
        out[h] = s[~s.index.duplicated(keep="last")]
    return out


def load_or_fetch_hub_series():
    """Per-hub full 15-min series, from the gitignored cache or a one-time bundle re-download."""
    os.makedirs(HUB_PKL_DIR, exist_ok=True)
    cached = {h: os.path.join(HUB_PKL_DIR, f"{h}.pkl") for h in HUBS}
    if all(os.path.exists(p) for p in cached.values()):
        return {h: pd.read_pickle(p) for h, p in cached.items()}
    acc = {h: [] for h in HUBS}
    for b in list_bundles():
        try:
            parts = bundle_to_hubs(_get(b["href"], timeout=180).content, HUBS)
        except Exception as e:
            print(f"loc: {b['name']} FAILED ({e})", flush=True)
            continue
        for h, s in parts.items():
            if len(s):
                acc[h].append(s)
        print(f"loc: {b['name']} -> " + ", ".join(f"{h}:{len(s)}" for h, s in parts.items()), flush=True)
    series = {}
    for h in HUBS:
        if not acc[h]:
            continue
        s = pd.concat(acc[h]).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        s.name = f"{h}_rt_spp"
        s.to_pickle(cached[h])
        series[h] = s
    return series


def build():
    series = load_or_fetch_hub_series()
    prices = {h: s[(s.index.year >= Y_LO) & (s.index.year <= Y_HI)] for h, s in series.items()}
    coords = {p["id"]: {"lon": p["lon"], "lat": p["lat"]} for p in map_data.HUB_POINTS}
    return LR.build_locational(prices, coords, duration_h=2.0)


if __name__ == "__main__":
    import time
    t = time.time()
    result = build()
    with open(RESULT_JSON, "w") as f:
        json.dump(result, f)
    print(f"\nlocational built in {time.time() - t:.0f}s -> {RESULT_JSON}")
    print("years:", result.get("years"))
    print("mean $/MW-yr by hub:", result.get("mean_by_hub"))
    print("rev scale:", result.get("rev_min"), "-", result.get("rev_max"))
    print("dropped partial years:", result.get("dropped_partial_years"))
    for y in ("2020", "2021"):
        fr = result.get("frames", {}).get(y, [])
        print(f"  {y}: " + " | ".join(
            f"{p['hub']} ${int(p['rev']):,} maxP${int(p['max_price']):,} top10={p['top10_share_pct']}%"
            for p in fr))
