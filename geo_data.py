"""
geo_data.py  —  Phase 1 of the map architecture: the geography layer.

"Everything is connected through latitude/longitude." Prices come from ERCOT; COORDINATES
come from public GIS datasets. This module ingests the real ones:

  BATTERIES + PLANTS : EIA Form 860M (monthly generator inventory). Every US generator with
                       plant name, operator, nameplate MW, technology, county, and lat/long.
                       Batteries = technology contains "Batteries". Filtered to Texas + ERCOT.
  CITIES             : a fixed table of Texas cities (name, county, population, lat/long) —
                       Census-sourced values, embedded because they never change.
  COUNTIES           : derived from the EIA county field (every plant carries its county).

HONEST RULES (same as map_data.py, enforced in code):
  * No fabricated coordinates. A row without a real lat/long is DROPPED, never guessed.
  * Every point carries `precision`: "asset_exact" (EIA-reported plant coordinate) or
    "city_point" (city centroid, not a load location).
  * NOT INCLUDED, deliberately: data centers (no authoritative public dataset — announced
    sites only, which would imply a completeness we don't have) and city-level power
    delivery (ERCOT publishes load by WEATHER ZONE, not by city — a city-load layer would
    be invented). Those wait for real data or stay out.

Requires a free EIA API key (api.eia.gov/register) in env EIA_API_KEY.
    python geo_data.py fetch     # pull EIA-860M -> data_archive/geo/{batteries,plants}.pkl
    python geo_data.py show      # what's cached
"""
import os
import sys

import numpy as np
import pandas as pd

GEO_DIR = os.path.join("data_archive", "geo")
EIA_URL = "https://api.eia.gov/v2/electricity/operating-generator-capacity/data/"

# Texas cities: Census-sourced, embedded (static reference, honest centroids).
TX_CITIES = [
    {"name": "Houston", "county": "Harris", "population": 2314157, "lat": 29.7604, "lon": -95.3698},
    {"name": "San Antonio", "county": "Bexar", "population": 1434625, "lat": 29.4241, "lon": -98.4936},
    {"name": "Dallas", "county": "Dallas", "population": 1304379, "lat": 32.7767, "lon": -96.7970},
    {"name": "Austin", "county": "Travis", "population": 961855, "lat": 30.2672, "lon": -97.7431},
    {"name": "Fort Worth", "county": "Tarrant", "population": 918915, "lat": 32.7555, "lon": -97.3308},
    {"name": "El Paso", "county": "El Paso", "population": 678815, "lat": 31.7619, "lon": -106.4850},
    {"name": "Arlington", "county": "Tarrant", "population": 394266, "lat": 32.7357, "lon": -97.1081},
    {"name": "Corpus Christi", "county": "Nueces", "population": 317863, "lat": 27.8006, "lon": -97.3964},
    {"name": "Plano", "county": "Collin", "population": 285494, "lat": 33.0198, "lon": -96.6989},
    {"name": "Lubbock", "county": "Lubbock", "population": 257141, "lat": 33.5779, "lon": -101.8552},
    {"name": "Laredo", "county": "Webb", "population": 255205, "lat": 27.5306, "lon": -99.4803},
    {"name": "Irving", "county": "Dallas", "population": 256684, "lat": 32.8140, "lon": -96.9489},
    {"name": "Garland", "county": "Dallas", "population": 246018, "lat": 32.9126, "lon": -96.6389},
    {"name": "Frisco", "county": "Collin", "population": 219587, "lat": 33.1507, "lon": -96.8236},
    {"name": "McKinney", "county": "Collin", "population": 207507, "lat": 33.1972, "lon": -96.6398},
    {"name": "Amarillo", "county": "Potter", "population": 200393, "lat": 35.2220, "lon": -101.8313},
    {"name": "Grand Prairie", "county": "Dallas", "population": 196100, "lat": 32.7459, "lon": -96.9978},
    {"name": "Brownsville", "county": "Cameron", "population": 186738, "lat": 25.9017, "lon": -97.4975},
    {"name": "Killeen", "county": "Bell", "population": 153095, "lat": 31.1171, "lon": -97.7278},
    {"name": "Pasadena", "county": "Harris", "population": 148026, "lat": 29.6911, "lon": -95.2091},
    {"name": "Midland", "county": "Midland", "population": 132524, "lat": 31.9973, "lon": -102.0779},
    {"name": "Odessa", "county": "Ector", "population": 114428, "lat": 31.8457, "lon": -102.3676},
    {"name": "Waco", "county": "McLennan", "population": 143984, "lat": 31.5493, "lon": -97.1467},
    {"name": "Abilene", "county": "Taylor", "population": 129472, "lat": 32.4487, "lon": -99.7331},
    {"name": "San Angelo", "county": "Tom Green", "population": 99893, "lat": 31.4638, "lon": -100.4370},
    {"name": "Tyler", "county": "Smith", "population": 108573, "lat": 32.3513, "lon": -95.3011},
    {"name": "College Station", "county": "Brazos", "population": 120019, "lat": 30.6280, "lon": -96.3344},
    {"name": "Beaumont", "county": "Jefferson", "population": 114609, "lat": 30.0802, "lon": -94.1266},
]

_BATT_KEYS = ("batteries", "battery")


# ----------------------------- pure parsing core (fixture-testable) -----------------------------
def parse_eia(rows):
    """EIA-860M API rows -> clean generator DataFrame. Drops anything without real coords."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    ren = {"plantid": "plant_id", "plantName": "plant", "stateid": "state",
           "technology": "tech", "entityName": "operator", "county": "county",
           "nameplate-capacity-mw": "mw", "latitude": "lat", "longitude": "lon",
           "statusDescription": "status", "period": "period", "balancing-authority-code": "ba"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    for c in ("mw", "lat", "lon"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    need = [c for c in ("lat", "lon") if c in df.columns]
    if len(need) < 2:
        return pd.DataFrame()
    df = df.dropna(subset=["lat", "lon"])                     # no coords -> dropped, never guessed
    # Texas bounding box sanity: anything outside is bad data, not a Texas asset
    df = df[(df.lon.between(-107.0, -93.0)) & (df.lat.between(25.5, 36.8))]
    if "state" in df.columns:
        df = df[df["state"].astype(str).str.upper() == "TX"]
    df["precision"] = "asset_exact"
    keep = [c for c in ("plant_id", "plant", "operator", "tech", "county", "mw",
                        "lat", "lon", "status", "ba", "precision") for _ in [0] if c in df.columns]
    return df[keep].reset_index(drop=True)


def split_batteries(df):
    """Batteries vs other generation, by EIA technology string."""
    if df.empty or "tech" not in df.columns:
        return df.head(0), df
    t = df["tech"].astype(str).str.lower()
    mask = t.str.contains("|".join(_BATT_KEYS), na=False)
    return df[mask].reset_index(drop=True), df[~mask].reset_index(drop=True)


def county_rollup(df, value_col="mw"):
    """Per-county totals — the 'list all the counties' view, derived from real asset rows."""
    if df.empty or "county" not in df.columns:
        return pd.DataFrame()
    g = (df.groupby("county")
           .agg(assets=("county", "size"), mw=(value_col, "sum"),
                lat=("lat", "mean"), lon=("lon", "mean"))
           .reset_index().sort_values("mw", ascending=False))
    return g


def cities_table():
    df = pd.DataFrame(TX_CITIES)
    df["precision"] = "city_point"       # centroid, NOT a load-delivery location
    return df


# ----------------------------- live fetch (Mac) -----------------------------
def fetch_eia(api_key=None, period=None):
    """Pull EIA-860M operating generator capacity for Texas."""
    import requests
    key = api_key or os.environ.get("EIA_API_KEY")
    if not key:
        raise SystemExit("Missing EIA_API_KEY (free at api.eia.gov/register). Put it in ~/.zshenv.")
    out, offset = [], 0
    params = {
        "api_key": key, "frequency": "monthly", "data[0]": "nameplate-capacity-mw",
        "facets[stateid][]": "TX", "sort[0][column]": "period", "sort[0][direction]": "desc",
        "length": 5000, "offset": 0,
    }
    if period:
        params["start"] = period; params["end"] = period
    while True:
        params["offset"] = offset
        r = requests.get(EIA_URL, params=params, timeout=60)
        if r.status_code != 200:
            raise SystemExit(f"EIA API HTTP {r.status_code}: {r.text[:400]}")
        payload = r.json().get("response", {})
        rows = payload.get("data", [])
        out += rows
        total = int(payload.get("total", len(out)))
        offset += len(rows)
        if not rows or offset >= total or offset > 60000:
            break
    df = parse_eia(out)
    if df.empty:
        raise SystemExit("EIA returned rows but none had usable TX coordinates — send me a sample.")
    # keep only the latest period per generator (860M is a monthly snapshot)
    return df


def save(batteries, plants, cities):
    os.makedirs(GEO_DIR, exist_ok=True)
    batteries.to_pickle(os.path.join(GEO_DIR, "batteries.pkl"))
    plants.to_pickle(os.path.join(GEO_DIR, "plants.pkl"))
    cities.to_pickle(os.path.join(GEO_DIR, "cities.pkl"))
    return GEO_DIR


def load_geo():
    """Read cached geography; returns (batteries, plants, cities) or empties."""
    def _r(n):
        p = os.path.join(GEO_DIR, f"{n}.pkl")
        return pd.read_pickle(p) if os.path.exists(p) else pd.DataFrame()
    return _r("batteries"), _r("plants"), _r("cities")


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "fetch":
        df = fetch_eia()
        batt, plants = split_batteries(df)
        cities = cities_table()
        save(batt, plants, cities)
        print(f"EIA: {len(df)} TX generators with real coords")
        print(f"  batteries: {len(batt)}  ({batt['mw'].sum():,.0f} MW)")
        print(f"  other plants: {len(plants)} ({plants['mw'].sum():,.0f} MW)")
        print(f"  counties with batteries: {batt['county'].nunique()}")
        print(f"  cities: {len(cities)}")
        print(batt.head(8)[["plant", "operator", "county", "mw", "lat", "lon"]].to_string(index=False))
    elif cmd == "show":
        b, p, c = load_geo()
        print(f"cached: {len(b)} batteries, {len(p)} plants, {len(c)} cities in {GEO_DIR}")
    else:
        # Fixture in the EIA API's shape: real-ish rows + junk that MUST be dropped.
        rows = [
            {"plantid": "1", "plantName": "Angleton BESS", "stateid": "TX", "county": "Brazoria",
             "technology": "Batteries", "entityName": "Some Owner", "nameplate-capacity-mw": "100",
             "latitude": "29.17", "longitude": "-95.43", "statusDescription": "Operating"},
            {"plantid": "2", "plantName": "Permian Storage", "stateid": "TX", "county": "Ector",
             "technology": "Batteries", "entityName": "Owner B", "nameplate-capacity-mw": "200",
             "latitude": "31.85", "longitude": "-102.37", "statusDescription": "Operating"},
            {"plantid": "3", "plantName": "Big Gas CC", "stateid": "TX", "county": "Harris",
             "technology": "Natural Gas Fired Combined Cycle", "entityName": "Owner C",
             "nameplate-capacity-mw": "800", "latitude": "29.75", "longitude": "-95.36"},
            {"plantid": "4", "plantName": "Wind Ranch", "stateid": "TX", "county": "Ector",
             "technology": "Onshore Wind Turbine", "entityName": "Owner D",
             "nameplate-capacity-mw": "300", "latitude": "31.90", "longitude": "-102.10"},
            {"plantid": "5", "plantName": "NO COORDS", "stateid": "TX", "county": "Travis",
             "technology": "Batteries", "entityName": "Owner E", "nameplate-capacity-mw": "50",
             "latitude": None, "longitude": None},                       # must be dropped
            {"plantid": "6", "plantName": "Arizona Plant", "stateid": "AZ", "county": "Maricopa",
             "technology": "Batteries", "entityName": "Owner F", "nameplate-capacity-mw": "75",
             "latitude": "33.45", "longitude": "-112.07"},                # wrong state -> dropped
        ]
        df = parse_eia(rows)
        assert len(df) == 4, f"expected 4 usable TX rows, got {len(df)}"
        assert "NO COORDS" not in df["plant"].values, "row without coords must be dropped, not guessed"
        assert "Arizona Plant" not in df["plant"].values, "non-TX must be filtered"
        assert (df["precision"] == "asset_exact").all()
        batt, plants = split_batteries(df)
        assert len(batt) == 2 and len(plants) == 2, f"battery split wrong: {len(batt)}/{len(plants)}"
        assert set(batt["plant"]) == {"Angleton BESS", "Permian Storage"}
        cr = county_rollup(batt)
        assert list(cr["county"]) == ["Ector", "Brazoria"], "county rollup must sort by MW desc"
        assert cr[cr.county == "Ector"].mw.iloc[0] == 200
        c = cities_table()
        assert len(c) >= 25 and (c["precision"] == "city_point").all()
        assert c[c.name == "Houston"]["population"].iloc[0] > 2_000_000
        assert all(-107 < x < -93 for x in c["lon"]) and all(25 < y < 37 for y in c["lat"])
        print("fixture self-test PASSED")
        print(f"  parsed 4/6 rows (dropped: no-coords, non-TX) | batteries 2, plants 2")
        print(f"  county rollup: {dict(zip(cr.county, cr.mw))}")
        print(f"  cities: {len(c)} TX cities embedded (Census, centroids)")
        print("\n  live: export EIA_API_KEY then  python geo_data.py fetch")
