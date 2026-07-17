"""
constraintarcs_run.py  —  pre-compute the deployable constraint-arc payload from the 90-day SCED
window + the augmented substation registry (base GIS + curated crosswalk).

AGGREGATE-FIRST: the map's default view is 90 days of BINDING-FREQUENCY arcs — for each placeable
line (both endpoints resolved to a real coordinate), how often it bound and its mean shadow price.
This is always populated (the ~congested corridors), unlike a live snapshot which is often empty.
A live-now mode (served by the endpoint) places the current SCED snapshot and honestly shows zero
when nothing placeable is binding.

Writes constraintarcs_result.json (small, committed like the other *_result.json) holding the
aggregate arcs, a resolved-station coordinate table (for live-now placement without shipping the
full registry), coverage stats, and the ranked unmatched list (the roadmap).
"""
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

import constraint_arcs as CA
import station_crosswalk as XW
import substation_registry as SR
from constraint_report import binding_frame

SCED_PKL = os.path.join("data_archive", "constraints", "sced_90d.pkl")
RESULT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "constraintarcs_result.json")


def build():
    raw = pd.read_pickle(SCED_PKL)
    b = binding_frame(raw)
    aug = XW.augmented_registry(SR.load_registry())

    stations = list(pd.unique(pd.concat([b["fromStation"], b["toStation"]]).astype(str)))
    kv_by = {}
    for _, r in b.iterrows():
        kv_by[r["fromStation"]] = r.get("fromStationkV")
        kv_by[r["toStation"]] = r.get("toStationkV")
    matches, unmatched = CA.match_stations(stations, aug, min_score=0.88, kv_by_station=kv_by)
    resolved = {code: [round(m["lat"], 5), round(m["lon"], 5)] for code, m in matches.items()}

    total_intervals = int(b["SCEDTimeStamp"].nunique())
    b = b.copy()
    b["placed"] = b.apply(lambda r: r["fromStation"] in matches and r["toStation"] in matches, axis=1)
    placed = b[b["placed"]]

    # aggregate by physical line (unordered station pair) -> frequency + shadow price
    agg = defaultdict(lambda: {"rows": 0, "intervals": set(), "shadow": [], "kv": set(),
                               "constraints": set(), "util": []})
    pair_ends = {}
    for _, r in placed.iterrows():
        key = tuple(sorted([r["fromStation"], r["toStation"]]))
        a = agg[key]
        a["rows"] += 1
        a["intervals"].add(r["SCEDTimeStamp"])
        a["shadow"].append(float(r["ShadowPrice"]))
        if not pd.isna(r.get("fromStationkV")):
            a["kv"].add(int(r["fromStationkV"]))
        a["constraints"].add(str(r.get("ConstraintName")))
        if not pd.isna(r.get("value")) and not pd.isna(r.get("limit")) and r["limit"]:
            a["util"].append(abs(float(r["value"])) / float(r["limit"]))
        pair_ends[key] = (r["fromStation"], r["toStation"])

    arcs, nodes = [], []
    for key, a in agg.items():
        fs, ts = pair_ends[key]
        s_lat, s_lon = resolved[fs]
        t_lat, t_lon = resolved[ts]
        rec = {
            "from_station": fs, "to_station": ts,
            "source": [s_lon, s_lat], "target": [t_lon, t_lat],
            "bind_intervals": len(a["intervals"]),
            "bind_pct": round(100 * len(a["intervals"]) / total_intervals, 3),
            "rows": a["rows"],
            "mean_shadow": round(float(np.mean(a["shadow"])), 2),
            "max_shadow": round(float(np.max(a["shadow"])), 2),
            "mean_util": round(float(np.mean(a["util"])), 3) if a["util"] else None,
            "kv": sorted(a["kv"]),
            "constraints": sorted(a["constraints"])[:6],
        }
        # from==to (or identical coords) is a transformer/bus limit AT one station, not a line —
        # drawing it as an arc would be misleading, so it becomes a node marker instead.
        if fs == ts or (abs(s_lat - t_lat) < 1e-6 and abs(s_lon - t_lon) < 1e-6):
            rec.pop("target", None)
            rec["lon"], rec["lat"] = s_lon, s_lat
            nodes.append(rec)
        else:
            arcs.append(rec)
    arcs.sort(key=lambda x: -x["bind_intervals"])
    nodes.sort(key=lambda x: -x["bind_intervals"])

    # ranked unmatched roadmap (reuse the report's sole-blocker idea, condensed)
    from collections import Counter
    sole = Counter()
    for _, r in b.iterrows():
        f_ok, t_ok = r["fromStation"] in matches, r["toStation"] in matches
        if not f_ok and t_ok:
            sole[r["fromStation"]] += 1
        elif f_ok and not t_ok:
            sole[r["toStation"]] += 1
    roadmap = [{"code": c, "sole_blocker_rows": n} for c, n in sole.most_common(40)]

    return {
        "window": {"start": str(pd.to_datetime(b["SCEDTimeStamp"]).min())[:10],
                   "end": str(pd.to_datetime(b["SCEDTimeStamp"]).max())[:10],
                   "sced_intervals": total_intervals},
        "aggregate_arcs": arcs,
        "node_constraints": nodes,
        "resolved_stations": resolved,
        "coverage": {
            "stations_total": len(stations), "stations_resolved": len(matches),
            "station_match_pct": round(100 * len(matches) / len(stations), 1),
            "binding_rows": int(len(b)), "arc_rows_placed": int(placed.shape[0]),
            "arc_row_pct": round(100 * placed.shape[0] / len(b), 1),
            "placeable_lines": len(arcs), "node_constraints": len(nodes),
            "crosswalk_codes": sum(len(e.get("codes", [])) for e in XW.load_crosswalk()),
        },
        "roadmap_unmatched": roadmap,
        "labels": {
            "measured": ("Arcs are ERCOT SCED reported constraints — from/to station, limit, "
                         "actual flow, shadow price. Measured facts, not a model or an estimate."),
            "partial": ("Only constraints whose BOTH endpoints resolve to a real substation are "
                        "drawn (station match {}%). Unresolved stations are listed as the roadmap, "
                        "never placed at a guessed point.").format(
                            round(100 * len(matches) / len(stations), 1)),
            "aggregate": ("Default view: 90-day BINDING FREQUENCY — width = how often the line "
                          "bound, color = mean shadow price. Live-now shows the current snapshot "
                          "and is honestly empty when nothing placeable is binding."),
            "scope": ("A congested-grid layer: the report contains only binding/violated "
                      "constraints, not every ERCOT line. Not a complete power-flow map."),
        },
    }


if __name__ == "__main__":
    res = build()
    with open(RESULT_JSON, "w") as f:
        json.dump(res, f)
    c = res["coverage"]
    print(f"window {res['window']['start']}..{res['window']['end']} ({res['window']['sced_intervals']} SCED intervals)")
    print(f"coverage: {c['stations_resolved']}/{c['stations_total']} stations = {c['station_match_pct']}% | "
          f"arc-rows {c['arc_rows_placed']}/{c['binding_rows']} = {c['arc_row_pct']}% | "
          f"placeable lines: {c['placeable_lines']}")
    print(f"\ntop aggregate arcs (freq | mean$ | line):")
    for a in res["aggregate_arcs"][:12]:
        print(f"  {a['bind_pct']:>5.1f}% ({a['bind_intervals']:>5} intervals)  ${a['mean_shadow']:>7.0f} mean / ${a['max_shadow']:>7.0f} max  "
              f"{a['from_station']}->{a['to_station']} {a['kv']}kV")
    print(f"\nresult -> {RESULT_JSON} ({os.path.getsize(RESULT_JSON)//1024} KB)")
