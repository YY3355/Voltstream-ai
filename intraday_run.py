"""
intraday_run.py  —  pre-compute one recent day of NP6-86-CD SCED snapshots as placeable
constraint-arc frames, for the Map tab's intraday replay scrubber.

Each SCED run (~every 5 min) is a real snapshot: which lines were binding then, their flow,
direction and shadow price. This replays the day, hour by hour, reusing the exact snapshot-arc
rendering (which animates via Task B). Ships a small intraday_result.json (committed) so the
replay works on Fly without the 90-day cache.
"""
import json
import os

import pandas as pd

import constraint_arcs as CA
import station_crosswalk as XW
import substation_registry as SR
from constraint_report import binding_frame

SCED_PKL = os.path.join("data_archive", "constraints", "sced_90d.pkl")
RESULT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intraday_result.json")


def build(day=None):
    df = pd.read_pickle(SCED_PKL)
    b = binding_frame(df)
    b["_day"] = pd.to_datetime(b["SCEDTimeStamp"]).dt.normalize()
    day = pd.Timestamp(day) if day else b["_day"].max()      # most recent full day by default
    b = b[b["_day"] == day]
    reg = XW.augmented_registry(SR.load_registry())[["name", "lat", "lon"]]

    timestamps, frames = [], {}
    n_arc_snapshots = 0
    for ts, g in b.groupby("SCEDTimeStamp"):
        timestamps.append(str(ts))
        built = CA.build_arcs(CA.parse_constraints(g.assign(SCEDTimeStamp=ts)), reg)
        arcs = [{"from_station": a["from_station"], "to_station": a["to_station"],
                 "source": [round(a["source"][0], 5), round(a["source"][1], 5)],
                 "target": [round(a["target"][0], 5), round(a["target"][1], 5)],
                 "flow_mw": a["flow_mw"], "limit_mw": a["limit_mw"], "utilization": a["utilization"],
                 "shadow_price": a["shadow_price"], "direction": a["direction"],
                 "kv": a.get("kv"), "contingency": a.get("contingency"),
                 "constraint": a.get("constraint"), "type": a["type"]}
                for a in built.get("arcs", [])]
        if arcs:
            frames[str(ts)] = arcs
            n_arc_snapshots += 1
    timestamps.sort()
    return {
        "day": str(day.date()),
        "timestamps": timestamps,               # full SCED axis for the scrubber
        "frames": frames,                        # only snapshots WITH placeable arcs (rest = empty, honest)
        "n_snapshots": len(timestamps),
        "n_arc_snapshots": n_arc_snapshots,
        "note": ("Replay of REAL ERCOT SCED snapshots (NP6-86-CD), ~every 5 min through the day. "
                 "Each frame shows the measured binding constraints placeable to real substations; "
                 "snapshots with no placeable binding constraint are honestly empty."),
    }


if __name__ == "__main__":
    import sys
    res = build(sys.argv[1] if len(sys.argv) > 1 else None)
    with open(RESULT_JSON, "w") as f:
        json.dump(res, f)
    print(f"intraday day {res['day']}: {res['n_snapshots']} SCED snapshots, "
          f"{res['n_arc_snapshots']} with placeable arcs -> {RESULT_JSON} "
          f"({os.path.getsize(RESULT_JSON)//1024} KB)")
    # show the arc-count timeline (hourly)
    import collections
    by_hr = collections.Counter()
    for ts, arcs in res["frames"].items():
        by_hr[ts[11:13]] += len(arcs)
    print("arcs by hour:", {h: by_hr[h] for h in sorted(by_hr)})
