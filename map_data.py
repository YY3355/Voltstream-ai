"""
map_data.py  —  the geospatial layer: real ERCOT coordinates joined to live DART.

HONEST COORDINATE POLICY (the hard part of any grid map, and where most fakes are born):
prices from ERCOT do not arrive with lat/long. Every coordinate here is a REAL, documented
location, and each row carries a `precision` field saying how exact it is:
    "hub_region"  — placed at the population/geographic center of the hub's region. A trading
                    hub is an AVERAGE of many nodes, not a single point, so this is an honest
                    REGIONAL marker, not a physical bus. Labeled as such in the popup.
    "node_exact"  — a specific settlement point at its verified coordinate (added later, only
                    when a real source is found — never guessed).

The table is structured so resource nodes drop in later as new rows with the same schema;
nothing about the endpoint or the map changes when they do. No coordinate is fabricated —
if we don't know where a point is, it does not go on the map.
"""
import numpy as np

# Regional centers for ERCOT's four trading-hub zones. These are documented Texas locations
# chosen as honest regional markers for each hub's footprint (a hub is a many-node average).
#   HB_HOUSTON — Houston metro (Harris County)
#   HB_NORTH   — Dallas-Fort Worth metroplex (North zone)
#   HB_SOUTH   — South Texas, near San Antonio/Corpus corridor
#   HB_WEST    — West Texas / Permian-Panhandle wind belt (near San Angelo/Midland)
HUB_POINTS = [
    {"id": "HB_HOUSTON", "label": "Houston Hub",     "lon": -95.37, "lat": 29.76,
     "precision": "hub_region", "region": "Houston metro"},
    {"id": "HB_NORTH",   "label": "North Hub",       "lon": -97.03, "lat": 32.90,
     "precision": "hub_region", "region": "Dallas-Fort Worth"},
    {"id": "HB_SOUTH",   "label": "South Hub",       "lon": -98.49, "lat": 29.42,
     "precision": "hub_region", "region": "South Texas (San Antonio corridor)"},
    {"id": "HB_WEST",    "label": "West Hub",         "lon": -100.44, "lat": 31.46,
     "precision": "hub_region", "region": "West Texas (San Angelo / Permian)"},
]

# Future: resource nodes go here as {"id","label","lon","lat","precision":"node_exact","region"}
NODE_POINTS = []

TEXAS_CENTER = {"lon": -99.3, "lat": 31.2, "zoom": 5.4}


def coordinate_table():
    """All points we can honestly place. Hubs today; nodes append here later, same schema."""
    return HUB_POINTS + NODE_POINTS


def build_map(dart_result):
    """Join the coordinate table to a run_dart() result -> GeoJSON-ready map points.

    dart_result: the dict from dart_engine.run_dart() (has 'stats' per hub with DART mean,
    hit_rate_pct, etc.). We attach the live DART value to each coordinate we can place.
    Returns points + the fields the map styles on. Never invents a point without data.
    """
    if not dart_result or "error" in (dart_result or {}):
        return {"error": (dart_result or {}).get("error", "no DART data"),
                "center": TEXAS_CENTER, "points": []}
    stats = dart_result.get("stats", {})
    pts = []
    for row in coordinate_table():
        st = stats.get(row["id"])
        if st is None:
            continue                      # no live data for this point -> not drawn (honest)
        dart = st.get("mean")
        pts.append({
            "id": row["id"], "label": row["label"], "region": row["region"],
            "precision": row["precision"],
            "lon": row["lon"], "lat": row["lat"],
            "dart": dart,                                  # $/MWh, DA - RT average over window
            "abs_dart": abs(dart) if dart is not None else 0.0,
            "sign": "rich" if (dart or 0) > 0 else "cheap",  # DA rich vs cheap to RT
            "hit_rate_pct": st.get("hit_rate_pct"),
            "std": st.get("std"),
            "cum_1mw": st.get("cum_1mw"),
            "n_hours": st.get("n_hours"),
        })
    return {
        "center": TEXAS_CENTER,
        "points": pts,
        "window": dart_result.get("window"),
        "data_source": dart_result.get("data_source", "live ERCOT via gridstatus"),
        "note": ("Hub markers are honest REGIONAL centers, not physical buses — a trading hub "
                 "is an average of many nodes. Resource-node points will be added only with "
                 "verified coordinates."),
    }


if __name__ == "__main__":
    # Fixture: a synthetic run_dart-shaped result -> verify the join, signs, and honesty rules.
    fake = {
        "stats": {
            "HB_HOUSTON": {"mean": 3.30, "hit_rate_pct": 61.0, "std": 8.1, "cum_1mw": 240.0, "n_hours": 72},
            "HB_NORTH":   {"mean": 0.00, "hit_rate_pct": 50.0, "std": 6.0, "cum_1mw": 0.0,   "n_hours": 72},
            "HB_WEST":    {"mean": -11.31, "hit_rate_pct": 38.0, "std": 20.4, "cum_1mw": -800.0, "n_hours": 72},
            # HB_SOUTH intentionally MISSING -> must not be drawn
        },
        "window": {"hours": 72}, "data_source": "LIVE ERCOT (fixture)",
    }
    m = build_map(fake)
    ids = [p["id"] for p in m["points"]]
    assert "HB_SOUTH" not in ids, "point without live data must be omitted, not faked"
    assert len(m["points"]) == 3, f"expected 3 placed points, got {len(ids)}"
    west = next(p for p in m["points"] if p["id"] == "HB_WEST")
    assert west["sign"] == "cheap" and west["abs_dart"] == 11.31, "West DA cheap to RT, size by |DART|"
    hou = next(p for p in m["points"] if p["id"] == "HB_HOUSTON")
    assert hou["sign"] == "rich", "Houston DA rich to RT"
    assert all(-107 < p["lon"] < -93 and 25 < p["lat"] < 37 for p in m["points"]), "coords must be in Texas"
    assert all(p["precision"] == "hub_region" for p in m["points"]), "hubs are regional markers"
    err = build_map({"error": "live DART pull unavailable"})
    assert "error" in err and err["points"] == [], "must pass through errors honestly, no fake map"
    print("fixture self-test PASSED")
    print(f"  placed {len(ids)} points: {ids} (HB_SOUTH correctly omitted — no data)")
    print(f"  West sign={west['sign']} |DART|=${west['abs_dart']}  Houston sign={hou['sign']}")
    print("  (fixture verifies the join + honesty rules; live map runs on the Mac via /api/map)")
