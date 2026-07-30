"""Task 3 — SABOTAGE test suite for the leakage guard.

The harness must be able to FAIL a cheat. These tests PASS by confirming the guard REJECTS planted
leaks (and admits only the legitimate feature set). Runnable standalone (no pytest needed):
    conda run -n volt python research/dart_forecast/tests/test_leakage.py
Also pytest-collectable (test_* functions).
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # research/dart_forecast
import dataset as ds
from leakage_guard import assert_no_leakage, LeakageError, decision_time

_FR = None
def frame():
    global _FR
    if _FR is None:
        _FR, _ = ds.build_hub_frame("HB_HOUSTON")
    return _FR

def _legit_feats(fr):
    return [c for c in fr.columns if c != "dart"]

# ---- 1. the legitimate feature set must PASS the guard ----
def test_legit_features_pass():
    fr = frame()
    res = assert_no_leakage(_legit_feats(fr), fr.index)
    assert res["ok"] and res["n_features"] == len(_legit_feats(fr))

# ---- 2. SABOTAGE (R1): plant dart_tomorrow (the target) -> unregistered -> REJECT ----
def test_sabotage_dart_tomorrow_rejected():
    fr = frame()
    feats = _legit_feats(fr) + ["dart_tomorrow"]       # planted leak: tomorrow's realized DART
    try:
        assert_no_leakage(feats, fr.index)
    except LeakageError as e:
        assert "dart_tomorrow" in str(e) and "R1" in str(e)
        return
    raise AssertionError("GUARD FAILED: it admitted the planted dart_tomorrow leak")

# ---- 3. SABOTAGE (R2): register a delivery-day feature -> available_at > decision_time -> REJECT ----
def test_sabotage_delivery_time_feature_rejected():
    fr = frame()
    feats = _legit_feats(fr) + ["rt_delivery_mean"]    # needs the delivery day's RT
    extra = {"rt_delivery_mean": {"group": "leak_delivery", "available_at": "delivery day RT"}}
    try:
        assert_no_leakage(feats, fr.index, extra_registry=extra)
    except LeakageError as e:
        assert "R2" in str(e) and "rt_delivery_mean" in str(e)
        return
    raise AssertionError("GUARD FAILED: it admitted a delivery-time feature (available_at > decision_time)")

# ---- 4. after removing the plant, the guard PASSES again (guard is not stuck-closed) ----
def test_plant_removed_passes():
    fr = frame()
    assert assert_no_leakage(_legit_feats(fr), fr.index)["ok"]

# ---- 5. sanity: decision_time is strictly before delivery for every row ----
def test_decision_time_before_delivery():
    fr = frame()
    dt = pd.DatetimeIndex(decision_time(fr.index))
    assert (dt < fr.index).all(), "decision_time must precede delivery for every row"

TESTS = [test_legit_features_pass, test_sabotage_dart_tomorrow_rejected,
         test_sabotage_delivery_time_feature_rejected, test_plant_removed_passes,
         test_decision_time_before_delivery]

if __name__ == "__main__":
    ok = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}"); ok += 1
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{ok}/{len(TESTS)} passed")
    sys.exit(0 if ok == len(TESTS) else 1)
