"""
constraint_report.py  —  frequency-ranked report of UNMATCHED ERCOT constraint station codes,
to target the smallest curation effort that lifts complete-arc coverage over the gate.

No UI, no coordinates invented. Reads the cached 90-day SCED constraint window + the substation
registry, finds which binding-constraint stations still can't be placed, and ranks them by how
much drawable-arc coverage each would unlock.
"""
import json
import os
import re
from collections import Counter, defaultdict

import pandas as pd

import constraint_arcs as CA
import substation_registry as SR

SCED_PKL = os.path.join("data_archive", "constraints", "sced_90d.pkl")
REPORT_JSON = os.path.join("data_archive", "constraints", "unmatched_ranked.json")


def binding_frame(df):
    """All binding, station-named constraint rows in the window (not just the latest snapshot)."""
    for c in ("limit", "value", "ShadowPrice", "fromStationkV", "toStationkV"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    b = df.dropna(subset=["fromStation", "toStation"]).copy()
    b = b[(b["fromStation"].astype(str).str.strip() != "") &
          (b["toStation"].astype(str).str.strip() != "")]
    b = b[b["ShadowPrice"].fillna(0) > 0]
    return b.reset_index(drop=True)


def alias_key(code):
    """Collapse obvious variants of one physical station: strip separators + trailing bus/equip
    digits, so LEONCRK / LEON_CRK / LEON CRK -> LEONCRK and MV_WESL4 -> MVWESL."""
    s = re.sub(r"[^A-Z0-9]", "", str(code).upper())
    s = re.sub(r"\d+$", "", s)                     # trailing bus/equipment number
    return s


def build_report():
    df = pd.read_pickle(SCED_PKL)
    b = binding_frame(df)
    reg = SR.load_registry()
    stations = list(pd.unique(pd.concat([b["fromStation"], b["toStation"]]).astype(str)))
    kv_by = {}
    for _, r in b.iterrows():
        kv_by[r["fromStation"]] = r.get("fromStationkV")
        kv_by[r["toStation"]] = r.get("toStationkV")
    matches, unmatched = CA.match_stations(stations, reg, min_score=0.88, kv_by_station=kv_by)
    matched_set = set(matches)
    unmatched_set = set(unmatched)

    # per unmatched code: rows affected, counterparts, kv, top constraints/contingencies,
    # and the KEY number — rows where THIS code is the ONLY missing endpoint (its resolution
    # alone makes the arc drawable).
    rows_aff = Counter()
    only_missing = Counter()               # this code is the sole blocker on the row
    counterparts = defaultdict(set)
    kvs = defaultdict(set)
    con_names = defaultdict(Counter)
    cont_names = defaultdict(Counter)
    for _, r in b.iterrows():
        fs, ts = r["fromStation"], r["toStation"]
        f_ok, t_ok = fs in matched_set, ts in matched_set
        for code, other, ok_other, kv in ((fs, ts, t_ok, r.get("fromStationkV")),
                                           (ts, fs, f_ok, r.get("toStationkV"))):
            if code in unmatched_set:
                rows_aff[code] += 1
                counterparts[code].add(other)
                if kv and not pd.isna(kv):
                    kvs[code].add(int(kv))
                con_names[code][str(r.get("ConstraintName"))] += 1
                cont_names[code][str(r.get("ContingencyName"))] += 1
                # sole blocker: the OTHER endpoint is already matched
                if ok_other:
                    only_missing[code] += 1

    # alias grouping
    groups = defaultdict(list)
    for code in unmatched_set:
        groups[alias_key(code)].append(code)

    ranked = []
    for code in sorted(unmatched_set, key=lambda c: (-only_missing[c], -rows_aff[c])):
        ak = alias_key(code)
        ranked.append({
            "code": code,
            "rows_affected": rows_aff[code],
            "rows_sole_blocker": only_missing[code],     # arc-rows this code ALONE would unlock
            "unique_counterparts": len(counterparts[code]),
            "voltages_kv": sorted(kvs[code]),
            "top_constraints": [c for c, _ in con_names[code].most_common(3)],
            "top_contingencies": [c for c, _ in cont_names[code].most_common(3)],
            "alias_group": sorted(groups[ak]) if len(groups[ak]) > 1 else [],
        })

    total_rows = len(b)
    both_placed = sum(1 for _, r in b.iterrows()
                      if r["fromStation"] in matched_set and r["toStation"] in matched_set)
    return {
        "window": {"rows": total_rows,
                   "start": str(pd.to_datetime(b["SCEDTimeStamp"]).min()),
                   "end": str(pd.to_datetime(b["SCEDTimeStamp"]).max())},
        "stations_total": len(stations),
        "stations_matched": len(matched_set),
        "station_match_pct": round(100 * len(matched_set) / len(stations), 1) if stations else 0,
        "arc_rows_placed": both_placed,
        "arc_row_pct": round(100 * both_placed / total_rows, 1) if total_rows else 0,
        "unmatched_ranked": ranked,
    }


if __name__ == "__main__":
    rep = build_report()
    os.makedirs(os.path.dirname(REPORT_JSON), exist_ok=True)
    with open(REPORT_JSON, "w") as f:
        json.dump(rep, f, indent=2)
    w = rep["window"]
    print(f"window: {w['rows']} binding rows, {w['start'][:10]} -> {w['end'][:10]}")
    print(f"station match {rep['stations_matched']}/{rep['stations_total']} = {rep['station_match_pct']}% | "
          f"arc-row placement {rep['arc_rows_placed']}/{w['rows']} = {rep['arc_row_pct']}%")
    print(f"\nTOP UNMATCHED CODES (by arc-rows this code ALONE would unlock):")
    print(f"{'code':<11}{'sole':>6}{'rows':>7}{'cpts':>5}  kv           top constraint")
    cum = 0
    for r in rep["unmatched_ranked"][:25]:
        cum += r["rows_sole_blocker"]
        al = f"  aliases={r['alias_group']}" if r["alias_group"] else ""
        print(f"{r['code']:<11}{r['rows_sole_blocker']:>6}{r['rows_affected']:>7}{r['unique_counterparts']:>5}  "
              f"{str(r['voltages_kv']):<12} {(r['top_constraints'][0] if r['top_constraints'] else '')[:22]}{al}")
    tot_sole = sum(r["rows_sole_blocker"] for r in rep["unmatched_ranked"])
    print(f"\nsole-blocker rows total across all unmatched: {tot_sole}")
    print(f"-> resolving the top codes converts their sole-blocker rows into drawable arcs.")
