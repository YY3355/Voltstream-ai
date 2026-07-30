"""Task 3 — leakage guard (the available_at gate).

A feature is admissible ONLY if it is known at decision_time. This guard fails CLOSED, two ways:
  (R1) every feature must be REGISTERED (have an available_at provenance); unknown columns are
       rejected — no silent leak through an undeclared column.
  (R2) each registered feature's available_at(row) must be <= decision_time(row) for ALL rows.

decision_time(delivery_ts) = 15:00 CT on (delivery_date - 1 day)  [the live commit leg].
Group available_at rules (all <= decision_time by construction for admissible groups):
  da_d1 : the DAM for the delivery day clears before decision_time -> available_at = decision_time.
  lag   : freshest same-hour datum <= decision_time (Dg-1 for H<=14 else Dg-2) -> available_at = decision_time.
  clim  : static climatology snapshot -> available_at = -inf.
  cal   : deterministic calendar -> available_at = -inf.
A LEAK group (e.g. a feature that needs the delivery day itself) has available_at = delivery_ts,
which is strictly > decision_time -> rejected by R2. See tests/test_leakage.py for the sabotage.

SCOPE / division of labor (stated honestly): this guard enforces DECLARED provenance + timing. It
cannot detect a leak that is MISLABELED under an admissible group (e.g. future data smuggled in with
a "lag" tag) — it trusts the declared group. That residual risk is covered by the STATISTICAL
backstop in Task 8 (shuffled-target gate): if the pipeline extracts skill from permuted targets, a
hidden/mislabeled leak exists regardless of declarations. The two gates are complementary and both
are required.
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset import FEATURE_REGISTRY   # name -> {"group":..., "available_at":...}

DECISION_HOUR_CT = 15   # 15:00 CT on the day before delivery

class LeakageError(Exception):
    pass

def decision_time(delivery_index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(delivery_index)
    return (idx.normalize() - pd.Timedelta(days=1)) + pd.Timedelta(hours=DECISION_HOUR_CT)

def _available_at(group: str, delivery_index) -> pd.Series:
    """Per-row available_at timestamp for a feature group (vectorized)."""
    idx = pd.DatetimeIndex(delivery_index)
    if group == "da_d1":
        return pd.Series(decision_time(idx), index=range(len(idx)))          # cleared by decision_time
    if group == "lag":
        return pd.Series(decision_time(idx), index=range(len(idx)))          # freshest datum <= decision_time
    if group in ("clim", "cal"):
        return pd.Series([pd.Timestamp.min] * len(idx), index=range(len(idx)))
    if group == "leak_delivery":
        return pd.Series(idx, index=range(len(idx)))                         # needs the delivery day
    # unknown group -> treat as maximally-late (fail closed)
    return pd.Series([pd.Timestamp.max] * len(idx), index=range(len(idx)))

def assert_no_leakage(feature_cols, delivery_index, registry: dict | None = None,
                      extra_registry: dict | None = None) -> dict:
    """Raise LeakageError if any feature is unregistered (R1) or available_at > decision_time (R2)."""
    reg = dict(registry if registry is not None else FEATURE_REGISTRY)
    if extra_registry:
        reg.update(extra_registry)
    feature_cols = list(feature_cols)

    # R1 — provenance: every feature must be registered
    unregistered = [c for c in feature_cols if c not in reg]
    if unregistered:
        raise LeakageError(f"R1 unregistered feature(s) with no available_at provenance: {unregistered}")

    # R2 — timing: available_at(row) <= decision_time(row) for all rows
    dt = pd.Series(decision_time(delivery_index), index=range(len(delivery_index)))
    violations = {}
    for c in feature_cols:
        grp = reg[c]["group"]
        aa = _available_at(grp, delivery_index)
        viol = aa.values > dt.values
        if viol.any():
            violations[c] = {"group": grp, "n_rows_violating": int(viol.sum()),
                             "example_available_at": str(aa.values[np.argmax(viol)]),
                             "example_decision_time": str(dt.values[np.argmax(viol)])}
    if violations:
        raise LeakageError(f"R2 available_at > decision_time: {violations}")
    return {"ok": True, "n_features": len(feature_cols), "n_rows": len(delivery_index)}


if __name__ == "__main__":
    import dataset as ds
    fr, _ = ds.build_hub_frame("HB_HOUSTON")
    feats = [c for c in fr.columns if c != "dart"]
    print("guarding", len(feats), "features over", len(fr), "rows ...")
    print(assert_no_leakage(feats, fr.index))
