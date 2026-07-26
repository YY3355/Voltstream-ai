"""build_clim.py — snapshot the per-hub DART climatology baseline from VoltStream's archive.

Writes clim_result.json (committed, same pattern as decade_result.json / hedge). HONESTY: the DART
climatology needs DA *and* RT for the same hour, and those hourly PAIRS only exist over the rolling
archive window (RT reaches ~7 weeks, DA ~30 days). This is NOT a decade of coverage — the payload
labels the true paired span, and (month,hour) cells with n<30 are marked insufficient, not invented.
On a box with months/years of accumulated caches the same script fills the cells in; here it is thin
and says so. This is the baseline the future eval-harnessed model must beat.

NEVER writes into journal/. Run: conda run -n volt python build_clim.py
"""
import json
import os
from datetime import datetime, timezone
import pandas as pd
import desk_data
from desk_climatology import build_climatology

HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]
OUT = "clim_result.json"


def _pairs(hub: str, days: int = 400) -> pd.DataFrame:
    """Hourly DA/RT pairs for one hub: DA hourly (dart_cache) ∩ RT resampled to hourly (price_store)."""
    import price_store
    da = desk_data._da_hourly(hub)
    rt15, _ = price_store.get_prices_rolling(hub, days=days, include_today=False, fetch_missing=False)
    rt = pd.Series(rt15.values, index=desk_data._to_naive(rt15.index)).resample("h").mean()
    idx = da.index.intersection(rt.index)
    return pd.DataFrame({"ts": idx, "da": da.reindex(idx).values,
                         "rt": rt.reindex(idx).values}).dropna(subset=["da", "rt"])


def main():
    hubs = {}
    for hub in HUBS:
        df = _pairs(hub)
        clim = build_climatology(df, label=hub)
        n_ok = sum(1 for c in clim["cells"].values() if not c.get("insufficient"))
        hubs[hub] = clim
        print(f"{hub}: {clim['n_hours_total']} paired hours, "
              f"{clim['date_range'][0]}..{clim['date_range'][1]}, "
              f"{n_ok}/{len(clim['cells'])} (month,hour) cells >= {clim['min_samples_rule']} samples")

    spans = [h["date_range"] for h in hubs.values() if h["n_hours_total"]]
    pair_start = min(r[0] for r in spans) if spans else None
    pair_end = max(r[1] for r in spans) if spans else None
    total_hours = sum(h["n_hours_total"] for h in hubs.values())
    total_cells = sum(len(h["cells"]) for h in hubs.values())
    ok_cells = sum(1 for h in hubs.values() for c in h["cells"].values() if not c.get("insufficient"))

    result = {
        "kind": "climatology_baseline",
        "coverage_note": (
            "Empirical (month,hour) P(RT>DA) and DART quantiles from archived ERCOT settlements. "
            "Coverage is the hourly DA/RT PAIR span below — the rolling archive window, NOT a decade. "
            "Cells with n<30 samples are insufficient and render '—' downstream. No conditioning on "
            "weather/load/wind/day-type — this is the CLIMATOLOGY BASELINE the eval-harnessed model must beat."),
        "pair_coverage": {"start": pair_start, "end": pair_end,
                          "note": "hourly DA/RT overlap only; DA cache ~30d, RT rolling store deeper"},
        "totals": {"paired_hours": total_hours, "cells": total_cells, "cells_sufficient": ok_cells},
        "hubs": hubs,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fly_caveat": ("committed snapshot (like decade_result.json). Fly's ephemeral volume won't hold "
                       "the DA/RT caches, so the deployed app reads THIS snapshot rather than rebuilding."),
    }
    with open(OUT, "w") as f:
        json.dump(result, f, indent=1)
    print(f"wrote {OUT}: {total_hours} paired hours across {len(hubs)} hubs, "
          f"pair span {pair_start}..{pair_end}, {ok_cells}/{total_cells} cells sufficient")


if __name__ == "__main__":
    main()
