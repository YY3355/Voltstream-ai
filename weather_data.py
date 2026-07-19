"""
weather_data.py  —  Phase 2 of the map architecture: the weather layer.

WHY WEATHER IS THE RIGHT PHASE-2 LAYER: it is the only one that makes the map EXPLAIN the
market instead of just displaying it. The causal chain a desk actually watches:

    wind speed (Far West / West)  ->  wind generation  ->  NET LOAD (demand - wind - solar)
    ->  scarcity  ->  price

Your DART map shows West hub running cheap to North; this layer shows the *reason* moving in
real time. Temperature does the same on the load side (Texas summer peaks are temperature).

DATA: Open-Meteo — free, no API key, no meter, honest. Hourly forecast + current conditions
at any lat/lon. Pulled at the centroid of each of ERCOT's eight weather zones.

HONEST RULES:
  * Zone points are REGIONAL centroids (precision "zone_centroid") — one weather reading does
    not describe a zone spanning hundreds of miles. Labeled as a sample, not a field.
  * Nothing here is a price forecast. It is weather, plus the stated mechanism by which
    weather moves prices. The map draws the input; it does not claim the output.
  * No API key, so nothing to leak, nothing to bill.
"""
import os
import sys

import numpy as np
import pandas as pd

OM_URL = "https://api.open-meteo.com/v1/forecast"
CACHE = os.path.join("data_archive", "weather")

# ERCOT's eight weather zones, at documented regional centroids.
# Wind-heavy zones flagged: their wind speed is the net-load driver.
ZONES = [
    {"zone": "Far West",      "lat": 31.60, "lon": -103.20, "wind_heavy": True,
     "note": "Permian Basin — wind + oilfield load"},
    {"zone": "West",          "lat": 32.45, "lon": -100.40, "wind_heavy": True,
     "note": "Abilene / San Angelo wind belt"},
    {"zone": "North",         "lat": 34.20, "lon": -101.10, "wind_heavy": True,
     "note": "Panhandle — highest wind density"},
    {"zone": "North Central", "lat": 32.78, "lon": -96.80,  "wind_heavy": False,
     "note": "Dallas-Fort Worth — major load center"},
    {"zone": "East",          "lat": 32.35, "lon": -95.30,  "wind_heavy": False,
     "note": "East Texas"},
    {"zone": "South Central", "lat": 29.42, "lon": -98.49,  "wind_heavy": False,
     "note": "San Antonio / Austin corridor"},
    {"zone": "Coast",         "lat": 29.76, "lon": -95.37,  "wind_heavy": False,
     "note": "Houston — largest load pocket"},
    {"zone": "Southern",      "lat": 27.80, "lon": -97.40,  "wind_heavy": True,
     "note": "Coastal Bend — coastal wind"},
]


# ----------------------------- pure parsing core (fixture-testable) -----------------------------
def parse_openmeteo(zone_row, payload):
    """One Open-Meteo response -> a clean zone weather record. Drops anything unusable."""
    cur = (payload or {}).get("current") or {}
    hourly = (payload or {}).get("hourly") or {}
    temp = cur.get("temperature_2m")
    wind = cur.get("wind_speed_10m")
    if temp is None or wind is None:
        return None                                    # no reading -> no point, never invented
    times = hourly.get("time") or []
    t_series = hourly.get("temperature_2m") or []
    w_series = hourly.get("wind_speed_10m") or []
    n = min(len(times), len(t_series), len(w_series), 48)
    precip = cur.get("precipitation")                  # mm in the current period (0 when dry / absent)
    return {
        "zone": zone_row["zone"], "lat": zone_row["lat"], "lon": zone_row["lon"],
        "wind_heavy": zone_row["wind_heavy"], "note": zone_row["note"],
        "precision": "zone_centroid",
        "temp_f": round(float(temp) * 9 / 5 + 32, 1),
        "wind_mph": round(float(wind) * 0.621371, 1),
        "precip_mm": round(float(precip), 2) if precip is not None else 0.0,
        "forecast_hours": [str(t) for t in times[:n]],
        "forecast_temp_f": [round(float(x) * 9 / 5 + 32, 1) for x in t_series[:n]],
        "forecast_wind_mph": [round(float(x) * 0.621371, 1) for x in w_series[:n]],
    }


def wind_signal(records):
    """The market-relevant summary: how hard is it blowing in the wind-heavy zones?

    Not a prediction — a stated mechanism. High wind in the wind belt means more wind
    generation, lower net load, and (historically) softer West-hub prices / wider basis.
    """
    wh = [r for r in records if r.get("wind_heavy")]
    if not wh:
        return None
    avg = float(np.mean([r["wind_mph"] for r in wh]))
    # 48h look-ahead in the same zones
    fut = [r["forecast_wind_mph"] for r in wh if r.get("forecast_wind_mph")]
    fut_avg = float(np.mean([np.mean(f) for f in fut])) if fut else None
    if avg >= 20:
        state, mech = "strong", "high wind -> more wind generation -> lower net load"
    elif avg >= 12:
        state, mech = "moderate", "moderate wind -> normal net load contribution"
    else:
        state, mech = "light", "light wind -> less wind generation -> higher net load"
    return {
        "wind_belt_avg_mph": round(avg, 1),
        "wind_belt_48h_avg_mph": round(fut_avg, 1) if fut_avg is not None else None,
        "state": state,
        "mechanism": mech,
        "zones_counted": [r["zone"] for r in wh],
        "caveat": "weather only — the map draws the input, it does not forecast price",
    }


def build_weather(records):
    return {
        "zones": records,
        "signal": wind_signal(records),
        "source": "Open-Meteo (free, no key) at ERCOT weather-zone centroids",
        "note": ("Points are REGIONAL centroids — one reading samples a zone spanning "
                 "hundreds of miles. Not a weather field, and not a price forecast."),
    }


# ----------------------------- live fetch (Mac) -----------------------------
def fetch_weather():
    import requests
    out = []
    for z in ZONES:
        try:
            r = requests.get(OM_URL, params={
                "latitude": z["lat"], "longitude": z["lon"],
                "current": "temperature_2m,wind_speed_10m,precipitation",
                "hourly": "temperature_2m,wind_speed_10m",
                "forecast_days": 2, "timezone": "America/Chicago",
            }, timeout=30)
            if r.status_code != 200:
                continue
            rec = parse_openmeteo(z, r.json())
            if rec:
                out.append(rec)
        except Exception:
            continue                                   # a zone that fails is omitted, not faked
    if not out:
        raise SystemExit("Open-Meteo returned nothing usable for any zone.")
    return build_weather(out)


def run_weather(ttl_s=1800):
    """Cached top level (weather changes slowly; don't hammer the API)."""
    import json, time
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "current.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl_s:
        try:
            return json.load(open(p))
        except Exception:
            pass
    try:
        d = fetch_weather()
        json.dump(d, open(p, "w"))
        return d
    except Exception as e:
        if os.path.exists(p):
            return json.load(open(p))                  # stale beats nothing
        return {"error": f"weather unavailable ({e})", "zones": []}


# ----------------------------- per-county weather (TRUE per-county readings) -----------------------------
# Upgrade from the 8-zone sample: one REAL Open-Meteo reading at EACH of the 254 Texas county
# centroids. Honest caveat: a single centroid reading still doesn't resolve weather WITHIN a large
# county — but it is that county's own measurement, not a zone value inherited by 30 counties.
COUNTY_GEO = os.path.join("data_archive", "geo", "tx_counties.geojson")


def _flatten_coords(x, out):
    """Collect every [lon,lat] pair from a (possibly nested) GeoJSON coordinate array."""
    if isinstance(x, (list, tuple)):
        if len(x) == 2 and all(isinstance(v, (int, float)) for v in x):
            out.append((float(x[0]), float(x[1])))
        else:
            for e in x:
                _flatten_coords(e, out)


def county_centroids(geojson_path=None):
    """[{county,lat,lon}] — a representative point (mean of boundary vertices) per TX county."""
    import json
    path = geojson_path or COUNTY_GEO
    d = json.load(open(path))
    rows = []
    for f in d.get("features", []):
        pts = []
        _flatten_coords(f["geometry"]["coordinates"], pts)
        if not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        rows.append({"county": f["properties"]["NAME"], "lat": round(lat, 4), "lon": round(lon, 4)})
    return rows


def parse_county_current(county_row, cur):
    """One Open-Meteo 'current' block -> a clean per-county record. Drops anything unusable."""
    cur = cur or {}
    temp = cur.get("temperature_2m")
    wind = cur.get("wind_speed_10m")
    if temp is None or wind is None:
        return None                                    # no reading -> no county, never invented
    precip = cur.get("precipitation")
    return {
        "county": county_row["county"], "lat": county_row["lat"], "lon": county_row["lon"],
        "temp_f": round(float(temp) * 9 / 5 + 32, 1),
        "wind_mph": round(float(wind) * 0.621371, 1),
        "precip_mm": round(float(precip), 2) if precip is not None else 0.0,
    }


def fetch_county_weather(batch=100):
    """Query Open-Meteo for ALL county centroids using multi-location batching (~100/req -> ~3 reqs)."""
    import requests
    rows = county_centroids()
    out = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        try:
            r = requests.get(OM_URL, params={
                "latitude": ",".join(str(c["lat"]) for c in chunk),
                "longitude": ",".join(str(c["lon"]) for c in chunk),
                "current": "temperature_2m,wind_speed_10m,precipitation",
                "timezone": "America/Chicago",
            }, timeout=45)
            if r.status_code != 200:
                continue
            data = r.json()
            if isinstance(data, dict):                 # single-location responses aren't wrapped in a list
                data = [data]
            for row, loc in zip(chunk, data):
                rec = parse_county_current(row, (loc or {}).get("current"))
                if rec:
                    out.append(rec)
        except Exception:
            continue                                   # a failed batch is omitted, never faked
    if not out:
        raise SystemExit("Open-Meteo returned nothing usable for any county.")
    return {
        "counties": out, "n": len(out),
        "source": "Open-Meteo (free, no key) at Texas county centroids",
        "note": ("One current reading per county centroid — a single point does not resolve "
                 "weather within a large county, but it is that county's own measurement."),
    }


def run_county_weather(ttl_s=1800):
    """Cached top level for the per-county pull (30-min TTL; stale beats nothing)."""
    import json, time
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "counties.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl_s:
        try:
            return json.load(open(p))
        except Exception:
            pass
    try:
        d = fetch_county_weather()
        json.dump(d, open(p, "w"))
        return d
    except Exception as e:
        if os.path.exists(p):
            return json.load(open(p))
        return {"error": f"county weather unavailable ({e})", "counties": []}


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "county":
        d = run_county_weather(ttl_s=0)
        if "error" in d:
            print(d["error"]); sys.exit(1)
        cs = d["counties"]
        print(f"{len(cs)} Texas counties — {d['source']}")
        hot = sorted(cs, key=lambda c: -(c["temp_f"] or 0))[:3]
        windy = sorted(cs, key=lambda c: -(c["wind_mph"] or 0))[:3]
        print("  hottest:", ", ".join(f"{c['county']} {c['temp_f']}F" for c in hot))
        print("  windiest:", ", ".join(f"{c['county']} {c['wind_mph']}mph" for c in windy))
        print("  raining:", sum(1 for c in cs if (c["precip_mm"] or 0) > 0.1), "counties")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        d = run_weather(ttl_s=0)
        if "error" in d:
            print(d["error"]); sys.exit(1)
        print(f"{len(d['zones'])} ERCOT weather zones — {d['source']}\n")
        for z in sorted(d["zones"], key=lambda r: -r["wind_mph"]):
            tag = "WIND BELT" if z["wind_heavy"] else "         "
            print(f"  {z['zone']:<14} {tag}  {z['temp_f']:>5.1f}F  {z['wind_mph']:>5.1f} mph   {z['note']}")
        s = d["signal"]
        print(f"\nwind belt: {s['wind_belt_avg_mph']} mph now ({s['state']}), "
              f"{s['wind_belt_48h_avg_mph']} mph avg next 48h")
        print(f"mechanism: {s['mechanism']}")
    else:
        # Fixture in Open-Meteo's response shape, incl. a zone that must be dropped.
        def payload(t_c, w_kmh, precip=0.0):
            return {"current": {"temperature_2m": t_c, "wind_speed_10m": w_kmh, "precipitation": precip},
                    "hourly": {"time": [f"2026-07-16T{h:02d}:00" for h in range(24)],
                               "temperature_2m": [t_c] * 24, "wind_speed_10m": [w_kmh] * 24}}
        recs = []
        for z in ZONES:
            pl = payload(35.0, 48.0, precip=(2.5 if z["zone"] == "North" else 0.0)) if z["wind_heavy"] \
                else payload(38.0, 8.0)
            r = parse_openmeteo(z, pl)
            if r:
                recs.append(r)
        assert len(recs) == 8, f"expected 8 zones, got {len(recs)}"
        far = next(r for r in recs if r["zone"] == "Far West")
        assert far["temp_f"] == 95.0, f"C->F conversion wrong: {far['temp_f']}"
        assert abs(far["wind_mph"] - 29.8) < 0.2, f"kmh->mph wrong: {far['wind_mph']}"
        assert len(far["forecast_wind_mph"]) == 24
        # precipitation must flow through parse_openmeteo (T1)
        north = next(r for r in recs if r["zone"] == "North")           # given precip=2.5 above
        assert north["precip_mm"] == 2.5, f"precip must carry through: {north['precip_mm']}"
        assert all("precip_mm" in r for r in recs), "every zone record carries precip_mm"
        assert far["precip_mm"] == 0.0, "dry zone reads 0 mm"

        bad = parse_openmeteo(ZONES[0], {"current": {}, "hourly": {}})
        assert bad is None, "a zone with no reading must be dropped, not invented"
        # missing precipitation field defaults to 0.0, never crashes
        noprecip = parse_openmeteo(ZONES[0], {"current": {"temperature_2m": 30.0, "wind_speed_10m": 10.0},
                                              "hourly": {"time": [], "temperature_2m": [], "wind_speed_10m": []}})
        assert noprecip["precip_mm"] == 0.0, "absent precip -> 0.0"

        d = build_weather(recs)
        s = d["signal"]
        assert s["state"] == "strong" and "lower net load" in s["mechanism"], s
        assert set(s["zones_counted"]) == {z["zone"] for z in ZONES if z["wind_heavy"]}
        assert len(s["zones_counted"]) == 4, "four wind-belt zones"

        calm = [dict(r, wind_mph=5.0, forecast_wind_mph=[5.0] * 24) for r in recs]
        assert wind_signal(calm)["state"] == "light", "light wind must flip the mechanism"
        assert "higher net load" in wind_signal(calm)["mechanism"]
        assert all(r["precision"] == "zone_centroid" for r in recs)

        # --- per-county (T3): parse + centroid helpers, no network ---
        cc = parse_county_current({"county": "Harris", "lat": 29.8, "lon": -95.4},
                                  {"temperature_2m": 35.0, "wind_speed_10m": 48.0, "precipitation": 2.5})
        assert cc["temp_f"] == 95.0 and abs(cc["wind_mph"] - 29.8) < 0.2 and cc["precip_mm"] == 2.5, cc
        assert parse_county_current({"county": "X", "lat": 0, "lon": 0}, {}) is None, "no reading -> dropped"
        assert parse_county_current({"county": "X", "lat": 0, "lon": 0},
                                    {"temperature_2m": 30.0, "wind_speed_10m": 10.0})["precip_mm"] == 0.0
        flat = []
        _flatten_coords([[[-97.0, 31.0], [-96.0, 31.0], [-96.0, 32.0], [-97.0, 31.0]]], flat)
        assert flat == [(-97.0, 31.0), (-96.0, 31.0), (-96.0, 32.0), (-97.0, 31.0)], flat
        if os.path.exists(COUNTY_GEO):
            cents = county_centroids()
            assert len(cents) == 254, f"expected 254 county centroids, got {len(cents)}"
            assert all(-107 < c["lon"] < -93 and 25 < c["lat"] < 37 for c in cents), "centroids inside TX bbox"
            print(f"  per-county: 254 centroids computed, parse+units verified (C->F, km/h->mph)")

        print("fixture self-test PASSED")
        print(f"  8 zones parsed, unit conversions verified (C->F, km/h->mph)")
        print(f"  wind signal: strong={s['wind_belt_avg_mph']}mph -> '{s['mechanism']}'")
        print(f"  dropped-zone rule holds; 4 wind-belt zones drive the signal")
        print("\n  live (no key needed):  python weather_data.py fetch")
