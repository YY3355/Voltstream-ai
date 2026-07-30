"""Task 2 — walk-forward splitter (expanding window, monthly retrain, embargoed).

Contract (verified by assert_valid + the independent checker):
  * EXPANDING train window: train = all rows with ts < (test_start - embargo).
  * MONTHLY retrain steps: each test block is one calendar month.
  * STRICT temporal ordering: max(train ts) < min(test ts), with a gap >= embargo_days.
  * ZERO overlap: train and test positional indices are disjoint; test blocks are disjoint.
  * Deterministic: splits depend only on the index + params, no randomness.

Positional indices (iloc) are returned so callers do frame.iloc[split.train_pos] / [.test_pos].
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

@dataclass
class Split:
    fold_id: int
    train_pos: np.ndarray
    test_pos: np.ndarray
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    n_train: int
    n_test: int

    def summary(self) -> dict:
        return {"fold_id": self.fold_id, "n_train": self.n_train, "n_test": self.n_test,
                "train": [str(self.train_start), str(self.train_end)],
                "test":  [str(self.test_start), str(self.test_end)]}


def walk_forward_splits(index, embargo_days: int = 1, min_train_days: int = 365,
                        test_freq: str = "MS", max_folds: int | None = None) -> list[Split]:
    """Generate embargoed, expanding, monthly walk-forward splits over a DatetimeIndex.

    embargo_days   : gap enforced between train end and test start (>= 1).
    min_train_days : first test block only after the train span covers at least this many days.
    test_freq      : pandas offset for test-block starts ("MS" = month start).
    """
    if embargo_days < 1:
        raise ValueError("embargo_days must be >= 1 (constraint: embargo gap >= 1 day)")
    idx = pd.DatetimeIndex(index)
    if not idx.is_monotonic_increasing:
        order = np.argsort(idx.values)
        idx = idx[order]
    else:
        order = np.arange(len(idx))
    pos_of = order  # maps sorted position -> original positional index
    start = idx.min()
    embargo = pd.Timedelta(days=embargo_days)

    # candidate test-block starts = month starts strictly after start
    block_starts = pd.date_range(start.normalize().replace(day=1), idx.max(), freq=test_freq)
    splits: list[Split] = []
    fid = 0
    for ts_start in block_starts:
        ts_end = ts_start + pd.offsets.MonthBegin(1)          # [ts_start, ts_end)
        train_cut = ts_start - embargo                         # train must end before this
        train_mask = idx < train_cut
        test_mask = (idx >= ts_start) & (idx < ts_end)
        if not test_mask.any() or not train_mask.any():
            continue
        train_span_days = (idx[train_mask].max() - idx[train_mask].min()).days
        if train_span_days < min_train_days:
            continue
        tr = pos_of[np.where(train_mask)[0]]
        te = pos_of[np.where(test_mask)[0]]
        splits.append(Split(
            fold_id=fid,
            train_pos=np.sort(tr), test_pos=np.sort(te),
            train_start=idx[train_mask].min(), train_end=idx[train_mask].max(),
            test_start=idx[test_mask].min(),  test_end=idx[test_mask].max(),
            n_train=int(train_mask.sum()), n_test=int(test_mask.sum()),
        ))
        fid += 1
        if max_folds and fid >= max_folds:
            break
    return splits


def assert_valid(splits: list[Split], index, embargo_days: int = 1) -> dict:
    """Independently checkable invariants. Raises AssertionError on any violation."""
    idx = pd.DatetimeIndex(index)
    embargo = pd.Timedelta(days=embargo_days)
    prev_test_end = None
    seen_test = set()
    for s in splits:
        tr_ts, te_ts = idx[s.train_pos], idx[s.test_pos]
        # 1. zero positional overlap between train and test
        assert not (set(s.train_pos.tolist()) & set(s.test_pos.tolist())), f"fold {s.fold_id}: train/test overlap"
        # 2. strict chronology + embargo gap >= embargo_days
        gap = te_ts.min() - tr_ts.max()
        assert tr_ts.max() < te_ts.min(), f"fold {s.fold_id}: train_end >= test_start"
        assert gap >= embargo, f"fold {s.fold_id}: embargo gap {gap} < {embargo}"
        # 3. expanding: train always starts at the global start
        assert tr_ts.min() == idx.min(), f"fold {s.fold_id}: train start drifted (not expanding)"
        # 4. test blocks are disjoint across folds and advance in time
        key = (s.test_start, s.test_end)
        assert key not in seen_test, f"fold {s.fold_id}: duplicate test block"
        seen_test.add(key)
        if prev_test_end is not None:
            assert s.test_start > prev_test_end, f"fold {s.fold_id}: test block not advancing"
        prev_test_end = s.test_end
    return {"n_folds": len(splits), "ok": True}


if __name__ == "__main__":
    import os, sys, json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dataset as ds
    fr, meta = ds.build_hub_frame("HB_HOUSTON")
    splits = walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
    report = assert_valid(splits, fr.index, embargo_days=1)
    print(f"HB_HOUSTON: {report['n_folds']} monthly folds, embargo=1d, min_train=365d")
    for s in splits[:2] + splits[-2:]:
        print(" ", s.summary())
    # persist a compact split manifest for the record (positions are large; store summaries + counts)
    out = {"kind": "walk_forward_splits", "hub": "HB_HOUSTON", "embargo_days": 1,
           "min_train_days": 365, "test_freq": "MS", "git_sha": ds.git_sha(),
           "n_folds": len(splits), "folds": [s.summary() for s in splits]}
    dst = os.path.join(ds.REPO, "research/dart_forecast/splits_manifest.json")
    json.dump(out, open(dst, "w"), indent=2, default=str)
    print("assert_valid:", report, "-> wrote", dst)
