"""
constraint_arcs.py  —  Phase 3: flow arcs built from MEASURED data.

WHY THESE ARCS ARE HONEST. ERCOT's SCED Shadow Prices & Binding Transmission Constraints
report (NP6-86-CD) does not just name constraints — it reports, per SCED run:
    fromStation, toStation, fromStationkV, limit (MW), value (actual flow MW),
    ShadowPrice ($/MWh), ContingencyName, violatedMW
So an arc from station A to station B, width = flow/limit, color = shadow price, is a
picture of REPORTED FACTS. Not a model. Not an estimate.

THE ONE HARD PART: ERCOT names stations in cryptic abbreviations ("MGSES", "NLARSW",
"PILONCIL"). The map needs coordinates. That requires a substation registry (HIFLD /
OpenStreetMap / EIA) and fuzzy matching. This module does the matching and then enforces
the rule that keeps the map honest:

    AN ARC IS DRAWN ONLY IF BOTH ENDPOINTS MATCHED A REAL SUBSTATION.
    Unmatched constraints are COUNTED AND REPORTED, never placed at a guessed point.

Expect a partial match rate. A 40% match rate that is TRUE is worth more than 100%
coverage that is invented — and the unmatched list is itself the roadmap for improving the
registry.

SCOPE: this is a "congested grid" layer — the report only contains BINDING or violated
constraints, not every line in ERCOT. It is not a complete power-flow map, and does not
claim to be.
"""
import re

import numpy as np
import pandas as pd

# ----------------------------- parsing the real report -----------------------------
def parse_constraints(df: pd.DataFrame, binding_only=True):
    """NP6-86-CD frame -> clean, placeable constraint rows with utilization."""
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    need = ["fromStation", "toStation", "limit", "value", "ShadowPrice"]
    for c in need:
        if c not in d.columns:
            return pd.DataFrame()
    for c in ("limit", "value", "ShadowPrice", "maxShadowPrice", "violatedMW",
              "fromStationkV", "toStationkV"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    # rows without BOTH station names can never be placed -> dropped, never guessed
    d = d.dropna(subset=["fromStation", "toStation"])
    d = d[(d["fromStation"].astype(str).str.strip() != "") &
          (d["toStation"].astype(str).str.strip() != "")]
    d = d[d["limit"].notna() & (d["limit"] > 0) & d["value"].notna()]
    if binding_only:
        d = d[d["ShadowPrice"].fillna(0) > 0]        # actually binding this SCED run
    if d.empty:
        return d
    d["utilization"] = (d["value"].abs() / d["limit"]).clip(upper=1.5)
    d["direction"] = np.where(d["value"] >= 0, "source_to_target", "target_to_source")
    if "SCEDTimeStamp" in d.columns:
        d["ts"] = pd.to_datetime(d["SCEDTimeStamp"], errors="coerce")
        latest = d["ts"].max()
        d = d[d["ts"] == latest]                      # the current snapshot
    return d.reset_index(drop=True)


# ----------------------------- substation registry matching -----------------------------
_SUFFIXES = (" SUBSTATION", " SUB", " SWITCHING STATION", " SWITCH", " SW", " SES",
             " STATION", " PLANT", " ES", " TAP")


def normalize_station(name: str) -> str:
    """Canonicalize a station name for matching: upper, strip voltage/suffix noise."""
    if name is None:
        return ""
    s = str(name).upper().strip()
    s = re.sub(r"\b\d{2,3}\s?KV\b", " ", s)          # drop "345 KV"
    s = re.sub(r"[^A-Z0-9 ]", " ", s)                 # punctuation -> space
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _score(a: str, b: str) -> float:
    """Cheap similarity for station names (no external deps)."""
    from difflib import SequenceMatcher
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.replace(" ", "") == b.replace(" ", ""):
        return 0.99
    # an ERCOT abbreviation is often a prefix/initialism of the full GIS name
    if b.startswith(a) or a.startswith(b):
        return 0.9
    initials = "".join(w[0] for w in b.split() if w)
    if a == initials and len(a) >= 3:
        return 0.88
    return SequenceMatcher(None, a, b).ratio()


def match_stations(stations, registry: pd.DataFrame, min_score=0.88, kv_by_station=None):
    """Resolve ERCOT station names -> registry coordinates.

    registry: DataFrame with columns name, lat, lon (optionally kv, county).
    Returns (matches {station: {...}}, unmatched [names]) — no fuzzy guess below min_score
    is ever accepted, because a wrong coordinate is worse than a missing arc.
    """
    matches, unmatched = {}, []
    if registry is None or registry.empty:
        return matches, list(dict.fromkeys(stations))
    reg = registry.copy()
    reg["_norm"] = reg["name"].map(normalize_station)
    reg = reg[reg["_norm"] != ""]
    for raw in dict.fromkeys(stations):
        n = normalize_station(raw)
        if not n:
            unmatched.append(raw); continue
        exact = reg[reg["_norm"] == n]
        cand = None
        if len(exact):
            cand = exact.iloc[0]; sc = 1.0
        else:
            scores = reg["_norm"].map(lambda b: _score(n, b))
            i = scores.idxmax() if len(scores) else None
            sc = float(scores.max()) if len(scores) else 0.0
            if i is not None and sc >= min_score:
                cand = reg.loc[i]
        if cand is None:
            unmatched.append(raw); continue
        # voltage validation when we have it: a 345kV constraint shouldn't match a 138kV yard
        if kv_by_station and "kv" in reg.columns and not pd.isna(cand.get("kv")):
            want = kv_by_station.get(raw)
            if want and abs(float(cand["kv"]) - float(want)) > 1 and sc < 0.99:
                unmatched.append(raw); continue
        matches[raw] = {"name": cand["name"], "lat": float(cand["lat"]), "lon": float(cand["lon"]),
                        "score": round(float(sc), 3),
                        "kv": (None if pd.isna(cand.get("kv", np.nan)) else float(cand.get("kv")))}
    return matches, unmatched


# ----------------------------- arc payload -----------------------------
def build_arcs(constraints: pd.DataFrame, registry: pd.DataFrame, min_score=0.88):
    """Measured constraint flows -> deck.gl ArcLayer payload. Only fully-matched arcs."""
    if constraints is None or constraints.empty:
        return {"arcs": [], "n_constraints": 0, "n_placed": 0, "match_rate_pct": 0.0,
                "unplaced": [], "unmatched_stations": [],
                "note": "no binding constraints with station data in this snapshot"}
    kv_by = {}
    for _, r in constraints.iterrows():
        kv_by[r["fromStation"]] = r.get("fromStationkV")
        kv_by[r["toStation"]] = r.get("toStationkV")
    names = list(constraints["fromStation"]) + list(constraints["toStation"])
    matches, unmatched = match_stations(names, registry, min_score=min_score, kv_by_station=kv_by)

    arcs, unplaced = [], []
    for _, r in constraints.iterrows():
        a, b = matches.get(r["fromStation"]), matches.get(r["toStation"])
        if not a or not b:                            # THE RULE: both ends or no arc
            unplaced.append({"constraint": r.get("ConstraintName"),
                             "from": r["fromStation"], "to": r["toStation"],
                             "shadow_price": round(float(r["ShadowPrice"]), 2),
                             "missing": [s for s, m in (("from", a), ("to", b)) if not m]})
            continue
        arcs.append({
            "constraint": r.get("ConstraintName"), "contingency": r.get("ContingencyName"),
            "from_station": r["fromStation"], "to_station": r["toStation"],
            "source": [a["lon"], a["lat"]], "target": [b["lon"], b["lat"]],
            "kv": (None if pd.isna(r.get("fromStationkV")) else float(r.get("fromStationkV"))),
            "flow_mw": round(float(r["value"]), 1),
            "limit_mw": round(float(r["limit"]), 1),
            "utilization": round(float(r["utilization"]), 3),
            "shadow_price": round(float(r["ShadowPrice"]), 2),
            "violated_mw": (None if pd.isna(r.get("violatedMW")) else round(float(r["violatedMW"]), 1)),
            "direction": r["direction"],
            "match_score": round(min(a["score"], b["score"]), 3),
            "type": "reported_constraint_flow",       # MEASURED — never mix with estimates
        })
    n = len(constraints)
    return {
        "arcs": arcs,
        "n_constraints": int(n),
        "n_placed": len(arcs),
        "match_rate_pct": round(100 * len(arcs) / n, 1) if n else 0.0,
        "unplaced": unplaced[:50],
        "unmatched_stations": sorted(set(unmatched))[:50],
        "timestamp": (str(constraints["ts"].iloc[0]) if "ts" in constraints.columns else None),
        "labels": {
            "measured": ("REPORTED flows: ERCOT's SCED constraint report gives from/to station, "
                         "limit, and actual flow. These arcs are measured facts, not a model."),
            "partial": ("Only constraints whose BOTH endpoints resolve to a real substation are "
                        "drawn. Unmatched ones are listed, never placed at a guessed point."),
            "scope": ("A CONGESTED-GRID layer: the report contains only binding/violated "
                      "constraints, not every ERCOT line. Not a complete power-flow map."),
        },
    }


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    raw = pd.DataFrame([
        # binding, both stations known -> must be drawn
        {"SCEDTimeStamp": "2026-07-16T23:55:17", "ConstraintName": "NLARSW_PILONC1_1",
         "ContingencyName": "DFOAVLO5", "ShadowPrice": 171.15, "maxShadowPrice": 3500.0,
         "limit": 137.5, "value": 137.5, "violatedMW": 0.0, "fromStation": "NLARSW",
         "toStation": "PILONCIL", "fromStationkV": 138.0, "toStationkV": 138.0},
        # binding, near limit, both known -> drawn
        {"SCEDTimeStamp": "2026-07-16T23:55:17", "ConstraintName": "6945__A",
         "ContingencyName": "SRGRMGS5", "ShadowPrice": 42.0, "maxShadowPrice": 4500.0,
         "limit": 1361.0, "value": 1355.8, "violatedMW": -5.2, "fromStation": "MGSES",
         "toStation": "CATSW", "fromStationkV": 345.0, "toStationkV": 345.0},
        # NULL stations (the real BASE CASE row) -> must never be placed
        {"SCEDTimeStamp": "2026-07-16T23:55:17", "ConstraintName": "NE_LOB",
         "ContingencyName": "BASE CASE", "ShadowPrice": 0.0, "maxShadowPrice": 5251.0,
         "limit": 1944.8, "value": 1702.1, "violatedMW": -242.7, "fromStation": None,
         "toStation": None, "fromStationkV": 0.0, "toStationkV": 0.0},
        # binding but one station unknown to the registry -> reported unplaced, not guessed
        {"SCEDTimeStamp": "2026-07-16T23:55:17", "ConstraintName": "MYSTERY_1",
         "ContingencyName": "XYZ", "ShadowPrice": 900.0, "maxShadowPrice": 4500.0,
         "limit": 500.0, "value": -480.0, "violatedMW": 0.0, "fromStation": "ZZQQ9",
         "toStation": "CATSW", "fromStationkV": 345.0, "toStationkV": 345.0},
        # stale timestamp -> dropped (we draw the current snapshot)
        {"SCEDTimeStamp": "2026-07-16T20:00:00", "ConstraintName": "OLD_1",
         "ContingencyName": "OLD", "ShadowPrice": 50.0, "maxShadowPrice": 100.0,
         "limit": 100.0, "value": 90.0, "violatedMW": 0.0, "fromStation": "MGSES",
         "toStation": "CATSW", "fromStationkV": 345.0, "toStationkV": 345.0},
    ])
    c = parse_constraints(raw)
    assert len(c) == 3, f"expected 3 current binding+placeable rows, got {len(c)}"
    assert "NE_LOB" not in set(c["ConstraintName"]), "null-station row must be dropped"
    assert "OLD_1" not in set(c["ConstraintName"]), "stale snapshot must be dropped"
    mg = c[c["ConstraintName"] == "6945__A"].iloc[0]
    assert abs(mg["utilization"] - 0.9962) < 0.001, f"utilization math: {mg['utilization']}"
    myst = c[c["ConstraintName"] == "MYSTERY_1"].iloc[0]
    assert myst["direction"] == "target_to_source", "negative flow must flip direction"

    registry = pd.DataFrame([
        {"name": "NLARSW", "lat": 27.61, "lon": -99.49, "kv": 138.0},
        {"name": "PILONCIL SUBSTATION", "lat": 27.80, "lon": -99.20, "kv": 138.0},
        {"name": "MGSES", "lat": 32.20, "lon": -97.10, "kv": 345.0},
        {"name": "CAT SWITCHING STATION", "lat": 32.60, "lon": -96.40, "kv": 345.0},
    ])
    out = build_arcs(c, registry)
    assert out["n_constraints"] == 3
    assert out["n_placed"] == 2, f"only the two fully-matched arcs may be drawn: {out['n_placed']}"
    assert abs(out["match_rate_pct"] - 66.7) < 0.2, out["match_rate_pct"]
    assert len(out["unplaced"]) == 1 and out["unplaced"][0]["constraint"] == "MYSTERY_1"
    assert out["unplaced"][0]["missing"] == ["from"], "must say which end failed"
    assert "ZZQQ9" in out["unmatched_stations"], "unmatched station must be reported"
    assert all(a["type"] == "reported_constraint_flow" for a in out["arcs"])
    arc = next(a for a in out["arcs"] if a["constraint"] == "NLARSW_PILONC1_1")
    assert arc["source"] == [-99.49, 27.61] and arc["utilization"] == 1.0
    assert arc["shadow_price"] == 171.15

    assert normalize_station("CLEARSPRING 345 KV") == "CLEARSPRING"
    assert normalize_station("CLEAR SPRING SUB") == "CLEAR SPRING"
    assert _score("CATSW", normalize_station("CAT SWITCHING STATION")) >= 0.9  # abbrev prefix match

    empty = build_arcs(pd.DataFrame(), registry)
    assert empty["arcs"] == [] and empty["n_placed"] == 0

    print("fixture self-test PASSED")
    print(f"  parsed 3/5 rows (dropped: null-station BASE CASE, stale snapshot)")
    print(f"  placed {out['n_placed']}/{out['n_constraints']} arcs = {out['match_rate_pct']}% match rate")
    print(f"  unplaced reported honestly: {[u['constraint'] for u in out['unplaced']]} "
          f"(missing {out['unplaced'][0]['missing']})")
    print(f"  MGSES->CATSW: {mg['value']}MW / {mg['limit']}MW = {mg['utilization']:.1%} utilized")
    print("  (fixture verifies parsing + the both-ends-or-no-arc rule; live needs a HIFLD registry)")
