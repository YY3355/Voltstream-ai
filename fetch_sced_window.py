"""
fetch_sced_window.py  —  robust, resumable pull of NP6-86-CD SCED binding-constraint rows over a
long window. The 90-day one-shot pagination trips ERCOT's 60s read timeout; this slices the
window into 7-day chunks, retries each page, and caches per-chunk so a slow page never loses the
run. Concatenates to data_archive/constraints/sced_90d.pkl.
"""
import glob
import os
import time

import pandas as pd

import ercot_archiver as EA

OUT_DIR = os.path.join("data_archive", "constraints")
CHUNK_DIR = os.path.join(OUT_DIR, "chunks")
FINAL_PKL = os.path.join(OUT_DIR, "sced_90d.pkl")
BASE = EA.BASE
URL = f"{BASE}/np6-86-cd/shdw_prices_bnd_trns_const"


def _page(frm, to, page, tries=4):
    for a in range(tries):
        try:
            return EA._get(URL, params={"SCEDTimestampFrom": frm, "SCEDTimestampTo": to,
                                        "size": 1000, "page": page}, timeout=120).json()
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(min(2 ** a, 20))
    return {}


def fetch_chunk(frm_ts, to_ts):
    frm, to = frm_ts.strftime("%Y-%m-%dT00:00:00"), to_ts.strftime("%Y-%m-%dT00:00:00")
    rows, fields, page = [], None, 1
    while True:
        p = _page(frm, to, page)
        fields = fields or [f["name"] for f in (p.get("fields") or [])]
        rows += (p.get("data") or [])
        meta = p.get("_meta") or {}
        if page >= (meta.get("totalPages") or 1):
            break
        page += 1
    df = pd.DataFrame(rows, columns=fields)
    return df.rename(columns={"SCEDTimestamp": "SCEDTimeStamp", "constraintName": "ConstraintName",
                              "contingencyName": "ContingencyName", "shadowPrice": "ShadowPrice"})


def run(days=90, chunk_days=7):
    os.makedirs(CHUNK_DIR, exist_ok=True)
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    cur = start
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=chunk_days), end)
        cpath = os.path.join(CHUNK_DIR, f"{cur.date()}_{nxt.date()}.pkl")
        if os.path.exists(cpath):
            print(f"chunk {cur.date()}..{nxt.date()} cached", flush=True)
        else:
            t = time.time()
            df = fetch_chunk(cur, nxt)
            df.to_pickle(cpath)
            print(f"chunk {cur.date()}..{nxt.date()}: {len(df)} rows in {time.time()-t:.0f}s", flush=True)
        cur = nxt
    parts = [pd.read_pickle(f) for f in sorted(glob.glob(os.path.join(CHUNK_DIR, "*.pkl")))]
    full = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    full.to_pickle(FINAL_PKL)
    ts = pd.to_datetime(full["SCEDTimeStamp"], errors="coerce")
    print(f"\nTOTAL {len(full)} rows -> {FINAL_PKL} | span {ts.min()} -> {ts.max()} "
          f"({(ts.max()-ts.min()).days}d)")
    return full


if __name__ == "__main__":
    run()
