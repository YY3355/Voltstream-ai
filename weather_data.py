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
    return {
        "zone": zone_row["zone"], "lat": zone_row["lat"], "lon": zone_row["lon"],
        "wind_heavy": zone_row["wind_heavy"], "note": zone_row["note"],
        "precision": "zone_centroid",
        "temp_f": round(float(temp) * 9 / 5 + 32, 1),
        "wind_mph": round(float(wind) * 0.621371, 1),
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
                "current": "temperature_2m,wind_speed_10m",
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


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
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
        def payload(t_c, w_kmh):
            return {"current": {"temperature_2m": t_c, "wind_speed_10m": w_kmh},
                    "hourly": {"time": [f"2026-07-16T{h:02d}:00" for h in range(24)],
                               "temperature_2m": [t_c] * 24, "wind_speed_10m": [w_kmh] * 24}}
        recs = []
        for z in ZONES:
            pl = payload(35.0, 48.0) if z["wind_heavy"] else payload(38.0, 8.0)
            r = parse_openmeteo(z, pl)
            if r:
                recs.append(r)
        assert len(recs) == 8, f"expected 8 zones, got {len(recs)}"
        far = next(r for r in recs if r["zone"] == "Far West")
        assert far["temp_f"] == 95.0, f"C->F conversion wrong: {far['temp_f']}"
        assert abs(far["wind_mph"] - 29.8) < 0.2, f"kmh->mph wrong: {far['wind_mph']}"
        assert len(far["forecast_wind_mph"]) == 24

        bad = parse_openmeteo(ZONES[0], {"current": {}, "hourly": {}})
        assert bad is None, "a zone with no reading must be dropped, not invented"

        d = build_weather(recs)
        s = d["signal"]
        assert s["state"] == "strong" and "lower net load" in s["mechanism"], s
        assert set(s["zones_counted"]) == {z["zone"] for z in ZONES if z["wind_heavy"]}
        assert len(s["zones_counted"]) == 4, "four wind-belt zones"

        calm = [dict(r, wind_mph=5.0, forecast_wind_mph=[5.0] * 24) for r in recs]
        assert wind_signal(calm)["state"] == "light", "light wind must flip the mechanism"
        assert "higher net load" in wind_signal(calm)["mechanism"]
        assert all(r["precision"] == "zone_centroid" for r in recs)
        print("fixture self-test PASSED")
        print(f"  8 zones parsed, unit conversions verified (C->F, km/h->mph)")
        print(f"  wind signal: strong={s['wind_belt_avg_mph']}mph -> '{s['mechanism']}'")
        print(f"  dropped-zone rule holds; 4 wind-belt zones drive the signal")
        print("\n  live (no key needed):  python weather_data.py fetch")
