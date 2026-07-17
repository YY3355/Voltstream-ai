"""
substation_registry.py  —  a Texas substation coordinate registry for placing ERCOT constraint
arcs (constraint_arcs.py). Every arc endpoint must resolve to a REAL substation here, or the arc
is not drawn — so this registry is the ground truth, and honest coverage matters more than size.

SOURCES:
  * HIFLD "Electric Substations" (ArcGIS FeatureServer) — the primary registry: name, lat/lon,
    max voltage, county. Public infrastructure data.
  * OpenStreetMap via Overpass — fallback / supplement: named power=substation nodes+ways in the
    Texas bounding box. OSM sometimes carries the operator's local name that HIFLD lists as
    "UNKNOWN", so merging improves the match rate against ERCOT's abbreviations.

Cached to data_archive/registry/substations.pkl (gitignored). Columns: name, lat, lon, kv,
county, source.
"""
import os

import pandas as pd

REG_DIR = os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "registry")
REG_PKL = os.path.join(REG_DIR, "substations.pkl")

HIFLD_URL = ("https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/"
             "Electric_Substations/FeatureServer/0/query")
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter",
                 "https://overpass.kumi.systems/api/interpreter"]
UA = "voltstream-map/1.0 (ERCOT grid research)"
TX_BBOX = (25.5, -107.0, 36.8, -93.0)          # S, W, N, E


def _clean(df):
    if df.empty:
        return df
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["kv"] = pd.to_numeric(df.get("kv"), errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    df = df[(df["lon"].between(-107.0, -93.0)) & (df["lat"].between(25.5, 36.8))]   # Texas box
    df = df[df["name"].notna() & (df["name"].astype(str).str.strip() != "")]
    df["kv"] = df["kv"].where(df["kv"] > 0)                    # 0/neg -> unknown
    return df.reset_index(drop=True)


def fetch_hifld(state="TX"):
    """Paginated pull of HIFLD Electric Substations for one state."""
    import requests
    rows, offset = [], 0
    while True:
        r = requests.get(HIFLD_URL, params={
            "where": f"STATE='{state}'",
            "outFields": "NAME,LATITUDE,LONGITUDE,MAX_VOLT,COUNTY,STATUS",
            "f": "json", "resultOffset": offset, "resultRecordCount": 2000,
            "returnGeometry": "false",
        }, timeout=60, headers={"User-Agent": UA})
        j = r.json()
        feats = j.get("features", [])
        for f in feats:
            a = f.get("attributes", {})
            rows.append({"name": a.get("NAME"), "lat": a.get("LATITUDE"), "lon": a.get("LONGITUDE"),
                         "kv": a.get("MAX_VOLT"), "county": a.get("COUNTY"), "source": "HIFLD"})
        if len(feats) < 2000 or not j.get("exceededTransferLimit"):
            break
        offset += len(feats)
    return _clean(pd.DataFrame(rows))


def fetch_osm():
    """Named power=substation nodes+ways in the Texas bbox, via Overpass."""
    import requests
    s, w, n, e = TX_BBOX
    q = (f'[out:json][timeout:180];('
         f'node["power"="substation"]["name"]({s},{w},{n},{e});'
         f'way["power"="substation"]["name"]({s},{w},{n},{e}););out center tags;')
    r = None
    for url in OVERPASS_URLS:                                  # try mirrors; the main one throttles
        try:
            rr = requests.post(url, data={"data": q}, timeout=200, headers={"User-Agent": UA})
            if rr.status_code == 200 and rr.content[:1] in (b"{", b"["):
                r = rr
                break
        except Exception:
            continue
    if r is None:
        raise RuntimeError("all Overpass mirrors failed")
    rows = []
    for el in r.json().get("elements", []):
        t = el.get("tags", {})
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        kv = t.get("voltage", "")
        kv = kv.split(";")[0] if kv else None
        try:
            kv = float(kv) / 1000.0 if kv else None               # V -> kV
        except Exception:
            kv = None
        rows.append({"name": t.get("name"), "lat": lat, "lon": lon, "kv": kv,
                     "county": None, "source": "OSM"})
    return _clean(pd.DataFrame(rows))


def build_registry(with_osm=True):
    """HIFLD primary + OSM supplement, de-duplicated by (normalized name, rounded coord)."""
    parts = []
    try:
        h = fetch_hifld()
        parts.append(h)
        print(f"HIFLD: {len(h)} placeable TX substations")
    except Exception as e:
        print(f"HIFLD failed: {e}")
    if with_osm:
        try:
            o = fetch_osm()
            parts.append(o)
            print(f"OSM:   {len(o)} named TX substations")
        except Exception as e:
            print(f"OSM failed: {e}")
    if not parts:
        raise SystemExit("no registry source reachable")
    reg = pd.concat(parts, ignore_index=True)
    reg["_k"] = (reg["name"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
                 + "_" + reg["lat"].round(2).astype(str) + "_" + reg["lon"].round(2).astype(str))
    reg = reg.drop_duplicates("_k").drop(columns="_k").reset_index(drop=True)
    return reg


def load_registry(refresh=False, with_osm=True):
    if not refresh and os.path.exists(REG_PKL):
        return pd.read_pickle(REG_PKL)
    os.makedirs(REG_DIR, exist_ok=True)
    reg = build_registry(with_osm=with_osm)
    reg.to_pickle(REG_PKL)
    return reg


if __name__ == "__main__":
    import sys
    refresh = "refresh" in sys.argv
    with_osm = "no-osm" not in sys.argv
    reg = load_registry(refresh=refresh, with_osm=with_osm)
    named = reg[~reg["name"].astype(str).str.upper().str.startswith("UNKNOWN")]
    print(f"\nregistry: {len(reg)} substations ({len(named)} with real names, "
          f"{len(reg) - len(named)} UNKNOWN######)")
    print("by source:", reg["source"].value_counts().to_dict())
    print("with kv:", int(reg["kv"].notna().sum()))
    print("sample names:", list(named["name"].head(8)))
