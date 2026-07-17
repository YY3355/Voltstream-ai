"""
station_crosswalk.py  —  a curated, provenance-tracked map from ERCOT station CODES (the cryptic
abbreviations in the SCED constraint feed: MGSES, OLNEY, VENSW, ...) to VERIFIED coordinates.

WHY THIS EXISTS: ERCOT's constraint report names stations by internal codes with no public
code->name->coordinate table. Public GIS (HIFLD/OSM) has the coordinates under the FULL station
name. This crosswalk is the human-verified bridge: each entry ties one or more codes/aliases to a
real facility whose coordinate is sourced from an ERCOT/utility/PUCT document or corroborated by
independent references. NO coordinate is accepted from a city-name guess, and fuzzy matching is
NOT loosened — the crosswalk is authoritative EXACT matches layered on top of the registry.

crosswalk.json entry schema:
    {"canonical_name","codes":[...],"lat","lon","voltage_kv","county","utility",
     "source","confidence","review_status"}

Mechanism: each code becomes an exact-named registry row (score 1.0 in match_stations), so
constraint_arcs.build_arcs(constraints, augmented_registry) places it — precedence over fuzzy,
without editing the fixture-tested module.
"""
import json
import os

import pandas as pd

CROSSWALK_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crosswalk.json")


def load_crosswalk(path=CROSSWALK_JSON):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("entries", data) if isinstance(data, dict) else data


def crosswalk_rows(entries=None):
    """One registry-shaped row per code/alias, carrying the verified coordinate + provenance."""
    entries = load_crosswalk() if entries is None else entries
    rows = []
    for e in entries:
        if e.get("lat") is None or e.get("lon") is None:
            continue                                    # unresolved entry — never placed
        for code in e.get("codes", []):
            rows.append({"name": code, "lat": e["lat"], "lon": e["lon"],
                         "kv": e.get("voltage_kv"), "county": e.get("county"),
                         "source": "crosswalk", "canonical": e.get("canonical_name"),
                         "confidence": e.get("confidence"), "provenance": e.get("source")})
    return pd.DataFrame(rows)


def augmented_registry(base_registry, entries=None):
    """Base substation registry + crosswalk code-rows. Crosswalk rows exact-match the ERCOT
    codes, so they win over any fuzzy registry candidate."""
    cw = crosswalk_rows(entries)
    if cw.empty:
        return base_registry
    cols = [c for c in base_registry.columns if c in cw.columns] or ["name", "lat", "lon"]
    for c in base_registry.columns:
        if c not in cw.columns:
            cw[c] = None
    return pd.concat([cw[base_registry.columns.tolist()], base_registry], ignore_index=True)


if __name__ == "__main__":
    entries = load_crosswalk()
    resolved = [e for e in entries if e.get("lat") is not None]
    n_codes = sum(len(e.get("codes", [])) for e in resolved)
    print(f"crosswalk: {len(entries)} entries, {len(resolved)} resolved, {n_codes} codes/aliases")
    for e in resolved:
        print(f"  {'/'.join(e['codes']):<22} -> {e['canonical_name']:<26} "
              f"({e['lat']:.4f},{e['lon']:.4f}) {e.get('voltage_kv')}kV  "
              f"conf={e.get('confidence')} [{e.get('review_status')}]")
