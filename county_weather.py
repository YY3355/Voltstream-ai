"""
county_weather.py  —  honest county-resolution weather shading for the map.

THE HONESTY PROBLEM THIS SOLVES: Open-Meteo gives 8 readings (one per ERCOT weather zone
centroid), not 254 county readings. Coloring every county by its OWN weather would be
fabrication — 30+ counties sharing one sample point, dressed up as independent data.

THE HONEST VERSION: draw every Texas county's REAL boundary, and fill each county with its
ERCOT WEATHER ZONE's live temperature + rain. This is truthful — we state it is zone weather
shown at county resolution, not per-county measurement. The counties tile the zones, so the
zones become readable at county granularity, and the label says exactly what it is.

This module maps each county -> its zone (a fixed, documented assignment) and joins the live
zone weather (temp, precip) so the map layer can color county polygons.
"""
import numpy as np

# ERCOT weather-zone assignment by county. A county belongs to exactly one ERCOT weather zone;
# this is that assignment for the counties we can place with HIGH CONFIDENCE from ERCOT's
# documented weather-zone geography. Counties in genuinely ambiguous positions (the Panhandle /
# South Plains, where the Far West/North/West split is uncertain, and a few far-SW border
# counties) are DELIBERATELY LEFT OUT rather than guessed — they render outlined but uncolored,
# and /api/countyweather reports exactly which. No fabricated per-county classification.
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


def build_county_weather(weather_result, county_zone=None):
    """Join live zone weather -> per-county color/rain payload. Pure/testable.

    weather_result: run_weather() output (has 'zones' with temp_f, wind_mph, and — once the
    engine pulls it — precip). Returns per-county fills + the zone summary the legend uses.
    """
    cz = county_zone or COUNTY_ZONE
    zones = {z["zone"]: z for z in (weather_result or {}).get("zones", [])}
    if not zones:
        return {"counties": [], "zones": [], "note": "no live weather available"}
    counties = []
    for county, zone in cz.items():
        z = zones.get(zone)
        if z is None:
            continue                                  # zone missing live data -> county uncolored
        temp = z.get("temp_f")
        precip = z.get("precip_mm", 0.0) or 0.0
        raining = precip > 0.1
        col = temp_color(temp)
        if raining:                                   # rain tints toward deep blue, overrides heat
            col = [30, 60, max(120, col[2])]
        counties.append({
            "county": county, "zone": zone,
            "temp_f": temp, "precip_mm": round(float(precip), 2), "raining": bool(raining),
            "fill": col,
        })
    zone_summary = [{"zone": z["zone"], "temp_f": z.get("temp_f"),
                     "precip_mm": round(float(z.get("precip_mm", 0.0) or 0.0), 2),
                     "raining": (z.get("precip_mm", 0.0) or 0.0) > 0.1,
                     "fill": temp_color(z.get("temp_f"))}
                    for z in weather_result.get("zones", [])]
    return {
        "counties": counties,
        "zones": zone_summary,
        "n_counties": len(counties),
        "label": ("County outlines are real boundaries; fill is each county's ERCOT WEATHER "
                  "ZONE live temperature (blue cool -> red hot), blue where the zone reports "
                  "rain. This is ZONE weather at county resolution — 8 real readings mapped to "
                  "counties, NOT per-county measurement."),
    }


if __name__ == "__main__":
    # Fixture: a run_weather-shaped result with temp + precip per zone.
    wr = {"zones": [
        {"zone": "Coast", "temp_f": 95.0, "precip_mm": 0.0},
        {"zone": "Far West", "temp_f": 104.0, "precip_mm": 0.0},
        {"zone": "North", "temp_f": 72.0, "precip_mm": 3.2},          # raining
        {"zone": "South Central", "temp_f": 88.0, "precip_mm": 0.0},
        {"zone": "West", "temp_f": 90.0, "precip_mm": 0.0},
        {"zone": "East", "temp_f": 85.0, "precip_mm": 0.0},
        {"zone": "North Central", "temp_f": 91.0, "precip_mm": 0.0},
        {"zone": "Southern", "temp_f": 93.0, "precip_mm": 0.0},
    ]}
    out = build_county_weather(wr)
    # every mapped county got a color
    assert out["n_counties"] == len(COUNTY_ZONE), f"all counties colored: {out['n_counties']}"
    harris = next(c for c in out["counties"] if c["county"] == "Harris")
    assert harris["zone"] == "Coast" and harris["temp_f"] == 95.0, "county inherits its zone's weather"
    # hotter zone -> redder fill
    fw = next(c for c in out["counties"] if c["county"] == "Ector")     # Far West, 104F
    assert fw["fill"][1] < harris["fill"][1], "hotter county must be redder (green channel drops toward red)"
    # raining county -> blue override
    wich = next(c for c in out["counties"] if c["county"] == "Wichita")  # North, raining
    assert wich["raining"] and wich["fill"][2] >= 120, "rain must tint blue"
    # a county whose zone has no data is dropped, not faked
    partial = build_county_weather({"zones": [{"zone": "Coast", "temp_f": 90.0, "precip_mm": 0}]})
    assert all(c["zone"] == "Coast" for c in partial["counties"]), "only zones with data color counties"
    assert "NOT per-county measurement" in out["label"], "honesty label present"
    # temp ramp monotonic at the extremes
    assert temp_color(105)[0] > temp_color(50)[0] and temp_color(50)[2] > temp_color(105)[2]
    print("fixture self-test PASSED")
    print(f"  {out['n_counties']} counties colored by their ERCOT zone's live weather")
    print(f"  Harris(Coast) {harris['temp_f']}F fill{harris['fill']} | "
          f"Ector(FarWest) {fw['temp_f']}F fill{fw['fill']} | Wichita(North) RAIN fill{wich['fill']}")
    print("  (fixture verifies the join + honesty; live needs county polygons + precip in weather_data)")
