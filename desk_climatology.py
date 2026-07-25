"""desk_climatology.py — the honest baseline behind the per-hour desk table.

WHAT THIS IS: empirical frequencies and quantiles of DART (RT - DA) computed
from VoltStream's own archived settlements, grouped by (month, hour). Every
number is a counted/measured fact from the archive.

WHAT THIS IS NOT (label in UI): a forecast model. No conditioning on weather,
load, wind, or day-type. This is the CLIMATOLOGY BASELINE that the future
probabilistic model (LightGBM quantiles + conformal) must beat in the eval
harness. Column header in the desk table: "Clim P(RT>DA)" — never "Model".

Input contract: DataFrame with columns [ts (hour-beginning, tz-aware or naive
consistent), da ($/MWh), rt ($/MWh)] for one settlement point.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timezone

QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
MIN_SAMPLES = 30  # below this, report None rather than a flimsy estimate


def build_climatology(df: pd.DataFrame, label: str = "") -> dict:
    """Returns {"cells": {(month,hour): {...}}, meta...} — all measured."""
    d = df.dropna(subset=["da", "rt"]).copy()
    d["dart"] = d["rt"] - d["da"]
    ts = pd.to_datetime(d["ts"])
    d["month"] = ts.dt.month
    d["hour"] = ts.dt.hour
    cells = {}
    for (m, h), g in d.groupby(["month", "hour"]):
        n = len(g)
        if n < MIN_SAMPLES:
            cells[f"{m}-{h}"] = {"n": n, "insufficient": True}
            continue
        q = g["dart"].quantile(QUANTILES)
        cells[f"{m}-{h}"] = {
            "n": int(n),
            "p_rt_gt_da": float((g["dart"] > 0).mean()),
            "dart_mean": float(g["dart"].mean()),
            "dart_q": {str(qq): float(q.loc[qq]) for qq in QUANTILES},
        }
    return {
        "label": label,
        "kind": "climatology_baseline",  # UI must render this label
        "n_hours_total": int(len(d)),
        "date_range": [str(ts.min())[:10], str(ts.max())[:10]],
        "min_samples_rule": MIN_SAMPLES,
        "note": ("empirical (month,hour) frequencies from archived settlements; "
                 "NOT a conditioned forecast model; baseline for eval harness"),
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cells": cells,
    }


def desk_rows(clim: dict, month: int, da_prices: dict[int, float],
              journal_calls: dict[int, str] | None = None) -> list[dict]:
    """Assemble per-hour desk-table rows for a delivery day.
    da_prices: {hour: DA price} from the archive/cache (real numbers only).
    journal_calls: {hour: 'long'|'short'|...} from dart_journal, if any.
    Columns with no real data are set to None — the UI renders '—', never 0."""
    rows = []
    for hour in range(24):
        cell = clim["cells"].get(f"{month}-{hour}", {})
        insufficient = cell.get("insufficient", False) or "p_rt_gt_da" not in cell
        rows.append({
            "hour": hour,
            "da_price": da_prices.get(hour),          # None if not published yet
            "clim_p_rt_gt_da": None if insufficient else cell["p_rt_gt_da"],
            "clim_dart_q05": None if insufficient else cell["dart_q"]["0.05"],
            "clim_dart_q50": None if insufficient else cell["dart_q"]["0.5"],
            "clim_dart_q95": None if insufficient else cell["dart_q"]["0.95"],
            "n_samples": cell.get("n", 0),
            "your_call": (journal_calls or {}).get(hour),
            "model_p": None,   # reserved: filled ONLY when eval-harnessed model ships
            "load_fcst": None, # reserved: ERCOT load forecast product not wired yet
            "wind_fcst": None, # reserved: ERCOT wind forecast product not wired yet
        })
    return rows
