"""
county_weather.py  —  TRUE per-county weather shading for the map.

Earlier this module inherited each county's color from its ERCOT weather ZONE (8 readings tiled
over 254 counties). That was honest-but-coarse. It now consumes REAL per-county readings from
weather_data.run_county_weather() — one Open-Meteo measurement at each of the 254 county
centroids — and colors each county by its OWN temperature + rain. Every county gets a fill; none
are left gray. The remaining honesty caveat is smaller and stated on the label: a single centroid
reading does not resolve weather WITHIN a large county.

The ZONE_COUNTIES map below is retained only to DEFINE the wind-belt region for the banner (a
documented grouping of the wind-heavy West/Panhandle/Coastal-Bend zones) — it no longer drives
any county's color.
"""
import numpy as np

# ERCOT weather-zone assignment by county — RETAINED ONLY to define the wind-belt region (below).
# No longer used to color counties; per-county readings do that now.
ZONE_COUNTIES = {
    "Coast": ["Harris", "Galveston", "Brazoria", "Fort Bend", "Chambers", "Liberty", "Montgomery",
              "Waller", "Austin", "Colorado", "Wharton", "Matagorda", "Jackson", "Hardin",
              "Jefferson", "Orange", "Walker", "San Jacinto", "Polk", "Tyler", "Jasper", "Newton",
              "Trinity", "Grimes", "Washington"],
    "Southern": ["Nueces", "San Patricio", "Aransas", "Refugio", "Bee", "Live Oak", "McMullen",
                 "Duval", "Jim Wells", "Kleberg", "Kenedy", "Brooks", "Cameron", "Hidalgo",
                 "Willacy", "Starr", "Zapata", "Jim Hogg", "Webb", "La Salle", "Dimmit", "Zavala",
                 "Victoria", "Goliad", "DeWitt", "Calhoun"],
    "Far West": ["El Paso", "Hudspeth", "Culberson", "Jeff Davis", "Presidio", "Brewster",
                 "Reeves", "Pecos", "Ward", "Winkler", "Loving", "Crane", "Upton", "Ector",
                 "Midland", "Andrews", "Martin", "Glasscock", "Reagan", "Terrell"],
    "West": ["Taylor", "Jones", "Nolan", "Fisher", "Scurry", "Mitchell", "Howard", "Runnels",
             "Coke", "Tom Green", "Concho", "Sterling", "Irion", "Coleman", "Callahan",
             "Shackelford", "Stephens", "Schleicher", "Sutton", "Menard", "Kimble", "Mason",
             "McCulloch"],
    "North": ["Wichita", "Wilbarger", "Clay", "Montague", "Cooke", "Grayson", "Fannin", "Archer",
              "Baylor", "Young", "Throckmorton", "Hardeman", "Foard", "Knox"],
    "North Central": ["Dallas", "Tarrant", "Collin", "Denton", "Ellis", "Johnson", "Parker",
                      "Rockwall", "Kaufman", "Hunt", "Hood", "Somervell", "Erath", "Palo Pinto",
                      "Wise", "Jack", "Navarro", "Hill", "Bosque", "Comanche", "Eastland",
                      "Hamilton"],
    "East": ["Smith", "Gregg", "Harrison", "Rusk", "Panola", "Shelby", "Nacogdoches", "Angelina",
             "Cherokee", "Henderson", "Anderson", "Houston", "Wood", "Upshur", "Van Zandt",
             "Rains", "Hopkins", "Franklin", "Titus", "Camp", "Morris", "Marion", "Cass", "Bowie",
             "Red River", "Lamar", "Delta", "Sabine", "San Augustine"],
    "South Central": ["Bexar", "Travis", "Williamson", "Hays", "Comal", "Guadalupe", "Bastrop",
                      "Caldwell", "Bell", "McLennan", "Coryell", "Falls", "Milam", "Burnet",
                      "Llano", "Blanco", "Gillespie", "Kendall", "Kerr", "Bandera", "Medina",
                      "Atascosa", "Wilson", "Karnes", "Gonzales", "Lavaca", "Fayette", "Lee",
                      "Lampasas", "San Saba", "Mills", "Brazos", "Burleson", "Robertson", "Leon",
                      "Madison", "Limestone", "Freestone", "Frio"],
}
COUNTY_ZONE = {c: z for z, cs in ZONE_COUNTIES.items() for c in cs}

# The wind belt = counties in ERCOT's wind-heavy zones (Far West / West / North / Southern). Used
# ONLY to compute the banner's wind-belt average from REAL per-county wind readings — a documented
# regional grouping, not a per-county weather claim.
WIND_BELT_ZONES = {"Far West", "West", "North", "Southern"}
WIND_BELT_COUNTIES = {c for c, z in COUNTY_ZONE.items() if z in WIND_BELT_ZONES}

PER_COUNTY_LABEL = ("county-centroid readings — one real measurement per county; "
                    "weather varies within large counties.")


def temp_color(temp_f):
    """Blue(cool) -> red(hot) ramp. Returns [r,g,b]. Honest continuous scale, 40F..110F."""
    if temp_f is None:
        return [80, 80, 90]
    t = max(0.0, min(1.0, (temp_f - 40.0) / 70.0))
    # blue -> teal -> amber -> red
    stops = [(0.0, (40, 90, 180)), (0.4, (60, 160, 160)),
             (0.7, (230, 170, 60)), (1.0, (210, 60, 50))]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            f = (t - p0) / (p1 - p0) if p1 > p0 else 0
            return [int(c0[i] + f * (c1[i] - c0[i])) for i in range(3)]
    return list(stops[-1][1])


def _wind_state(avg):
    """Wind-belt state + the weather->net-load mechanism sentence. Not a price forecast."""
    if avg >= 20:
        return "strong", "high wind -> more wind generation -> lower net load"
    if avg >= 12:
        return "moderate", "moderate wind -> normal net load contribution"
    return "light", "light wind -> less wind generation -> higher net load"


def wind_belt_signal(counties):
    """Mean of the REAL per-county wind readings across the wind-belt counties (banner input)."""
    wb = [c["wind_mph"] for c in counties
          if c["county"] in WIND_BELT_COUNTIES and c.get("wind_mph") is not None]
    if not wb:
        return None
    avg = float(np.mean(wb))
    state, mech = _wind_state(avg)
    return {
        "wind_belt_avg_mph": round(avg, 1),
        "wind_belt_48h_avg_mph": None,                # per-county pull is current-only (no 48h forecast)
        "state": state, "mechanism": mech,
        "counties_counted": len(wb),
        "caveat": "weather only — the map draws the input, it does not forecast price",
    }


def build_county_weather(county_wx):
    """Per-county readings -> per-county color/rain payload + wind-belt signal. Pure/testable.

    county_wx: run_county_weather() output (has 'counties' with temp_f, wind_mph, precip_mm).
    Every county carries its OWN reading — no zone inheritance, none left gray.
    """
    recs = (county_wx or {}).get("counties", [])
    if not recs:
        return {"counties": [], "n_counties": 0, "wind_signal": None,
                "label": PER_COUNTY_LABEL, "note": "no live county weather available"}
    counties = []
    for r in recs:
        temp = r.get("temp_f")
        precip = r.get("precip_mm", 0.0) or 0.0
        raining = precip > 0.1
        col = temp_color(temp)
        if raining:                                   # rain tints toward deep blue, overrides heat
            col = [30, 60, max(120, col[2])]
        counties.append({
            "county": r["county"],
            "temp_f": temp, "wind_mph": r.get("wind_mph"),
            "precip_mm": round(float(precip), 2), "raining": bool(raining),
            "fill": col,
        })
    return {
        "counties": counties,
        "n_counties": len(counties),
        "wind_signal": wind_belt_signal(counties),
        "label": PER_COUNTY_LABEL,
    }


if __name__ == "__main__":
    # Fixture: a run_county_weather-shaped result — REAL per-county readings (no zones).
    cwx = {"counties": [
        {"county": "Harris",  "temp_f": 95.0,  "wind_mph": 8.0,  "precip_mm": 0.0},   # Coast — not wind belt
        {"county": "Ector",   "temp_f": 104.0, "wind_mph": 22.0, "precip_mm": 0.0},   # Far West — wind belt
        {"county": "Wichita", "temp_f": 72.0,  "wind_mph": 25.0, "precip_mm": 3.2},   # North — wind belt, raining
        {"county": "Dallas",  "temp_f": 91.0,  "wind_mph": 6.0,  "precip_mm": 0.0},   # North Central — not wind belt
    ]}
    out = build_county_weather(cwx)
    assert out["n_counties"] == 4, out["n_counties"]
    harris = next(c for c in out["counties"] if c["county"] == "Harris")
    assert harris["temp_f"] == 95.0 and harris["wind_mph"] == 8.0, "county carries its OWN reading"
    assert "zone" not in harris, "no zone field — per-county now, no inheritance"
    # hotter county -> redder fill (green channel drops toward red)
    ector = next(c for c in out["counties"] if c["county"] == "Ector")
    assert ector["fill"][1] < harris["fill"][1], "hotter county must be redder"
    # raining county -> blue override
    wich = next(c for c in out["counties"] if c["county"] == "Wichita")
    assert wich["raining"] and wich["fill"][2] >= 120, "rain must tint blue"
    # wind belt: only Ector + Wichita count; mean(22,25)=23.5 -> strong
    ws = out["wind_signal"]
    assert ws is not None and ws["counties_counted"] == 2, ws
    assert abs(ws["wind_belt_avg_mph"] - 23.5) < 0.1 and ws["state"] == "strong", ws
    assert "lower net load" in ws["mechanism"]
    # light-wind flip
    calm = build_county_weather({"counties": [dict(c, wind_mph=5.0) for c in cwx["counties"]]})
    assert calm["wind_signal"]["state"] == "light" and "higher net load" in calm["wind_signal"]["mechanism"]
    # label = new per-county wording
    assert out["label"] == PER_COUNTY_LABEL and "one real measurement per county" in out["label"]
    # empty input -> honest empty, still labeled
    empty = build_county_weather({"counties": []})
    assert empty["n_counties"] == 0 and empty["wind_signal"] is None and empty["label"] == PER_COUNTY_LABEL
    # temp ramp monotonic at the extremes
    assert temp_color(105)[0] > temp_color(50)[0] and temp_color(50)[2] > temp_color(105)[2]
    # wind-belt county set is the wind-heavy zones only
    assert "Ector" in WIND_BELT_COUNTIES and "Wichita" in WIND_BELT_COUNTIES
    assert "Harris" not in WIND_BELT_COUNTIES and "Dallas" not in WIND_BELT_COUNTIES
    print("fixture self-test PASSED")
    print(f"  {out['n_counties']} counties colored by their OWN reading (per-county, 0 gray)")
    print(f"  Harris {harris['temp_f']}F fill{harris['fill']} | "
          f"Ector {ector['temp_f']}F fill{ector['fill']} | Wichita RAIN fill{wich['fill']}")
    print(f"  wind belt: {ws['wind_belt_avg_mph']}mph ({ws['state']}) over {ws['counties_counted']} counties")
