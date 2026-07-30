"""Task 7 — split-conformal calibration (CQR) per hub / hour-block.

Conformalized Quantile Regression (Romano et al. 2019): within each walk-forward fold, hold out the
LAST CAL_DAYS of TRAIN as a calibration set (disjoint from model fitting, still strictly before test).
Fit the quantile models on the proper-train; on calibration compute the CQR nonconformity score for a
central interval [q_lo, q_hi]:
    E_i = max(q_lo(x_i) - y_i,  y_i - q_hi(x_i))
Per HOUR-BLOCK b, the conformal radius is the finite-sample-corrected empirical quantile of {E_i}:
    Q_b = the k-th smallest E in block b, k = ceil((n_b + 1)(1 - alpha)).
Calibrated interval on test = [q_lo - Q_b, q_hi + Q_b]. Target: NOMINAL coverage (1-alpha), even if
the band widens — we report width before/after so a narrower-but-miscalibrated band can't masquerade.

Two intervals reported: 80% (q10/q90, alpha=.20) and 50% (q25/q75, alpha=.50). Lookahead-free:
calibration precedes test; fold-clim features are proper-train-only. Determinism inherited from model.py.
"""
from __future__ import annotations
import os, sys, json, time, math
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx, baselines as bl, model as M

OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")
CAL_DAYS = 90
N_BLOCK_HRS = 4                       # 6 four-hour blocks: block(h) = h // 4
INTERVALS = {"80": (0.10, 0.90, 0.20), "50": (0.25, 0.75, 0.50)}   # name -> (lo_tau, hi_tau, alpha)

def hour_block(hours):
    return (np.asarray(hours) // N_BLOCK_HRS).astype(int)

def conformal_radius(E, alpha):
    """Finite-sample conformal quantile: k-th smallest of E, k = ceil((n+1)(1-alpha))."""
    E = np.sort(np.asarray(E, float)); n = len(E)
    if n == 0:
        return np.inf
    k = math.ceil((n + 1) * (1 - alpha))
    k = min(max(k, 1), n)
    return float(E[k - 1])

def run_conformal(frame, splits, params, cal_days=CAL_DAYS, log_every=15):
    # pooled per interval: coverage/width before & after, per block and overall
    acc = {name: {"y": [], "lo0": [], "hi0": [], "lo1": [], "hi1": [], "blk": []} for name in INTERVALS}
    per_block_radius = {name: {b: [] for b in range(24 // N_BLOCK_HRS)} for name in INTERVALS}
    t0 = time.time()
    for i, s in enumerate(splits):
        tr = frame.iloc[s.train_pos]; te = frame.iloc[s.test_pos]
        cut = tr.index.max() - pd.Timedelta(days=cal_days)
        ptr = tr[tr.index < cut]; cal = tr[tr.index >= cut]
        if len(cal) < 200 or len(ptr) < 3000:
            continue
        cf_ptr, cf_cal = M.add_fold_clim(ptr, cal)
        _, cf_te = M.add_fold_clim(ptr, te)
        Xptr, Xcal, Xte = M._xy(ptr, cf_ptr), M._xy(cal, cf_cal), M._xy(te, cf_te)
        qm = M.fit_quantiles(Xptr, ptr["dart"].values, params)
        qcal = M.predict_quantiles(qm, Xcal); qte = M.predict_quantiles(qm, Xte)
        yb_cal = cal["dart"].values; yb_te = te["dart"].values
        blk_cal = hour_block(cal.index.hour); blk_te = hour_block(te.index.hour)
        for name, (lo, hi, alpha) in INTERVALS.items():
            E = np.maximum(qcal[lo] - yb_cal, yb_cal - qcal[hi])         # CQR score on calibration
            radii = {}
            for b in np.unique(blk_cal):
                radii[b] = conformal_radius(E[blk_cal == b], alpha)
                per_block_radius[name][int(b)].append(radii[b])
            # global fallback radius for any test block missing from calibration
            gr = conformal_radius(E, alpha)
            Qte = np.array([radii.get(b, gr) for b in blk_te])
            acc[name]["y"].append(yb_te)
            acc[name]["lo0"].append(qte[lo]); acc[name]["hi0"].append(qte[hi])          # before
            acc[name]["lo1"].append(qte[lo] - Qte); acc[name]["hi1"].append(qte[hi] + Qte)  # after
            acc[name]["blk"].append(blk_te)
        if log_every and (i % log_every == 0 or i == len(splits) - 1):
            print(f"  fold {i+1}/{len(splits)} test={s.test_start.date()} ({time.time()-t0:.0f}s)", flush=True)
    # aggregate
    out = {}
    for name, (lo, hi, alpha) in INTERVALS.items():
        y = np.concatenate(acc[name]["y"])
        lo0 = np.concatenate(acc[name]["lo0"]); hi0 = np.concatenate(acc[name]["hi0"])
        lo1 = np.concatenate(acc[name]["lo1"]); hi1 = np.concatenate(acc[name]["hi1"])
        blk = np.concatenate(acc[name]["blk"])
        cov0 = float(np.mean((y >= lo0) & (y <= hi0))); cov1 = float(np.mean((y >= lo1) & (y <= hi1)))
        w0 = float(np.mean(hi0 - lo0)); w1 = float(np.mean(hi1 - lo1))
        per_block = {}
        for b in np.unique(blk):
            m = blk == b
            per_block[int(b)] = {
                "hours": f"{b*N_BLOCK_HRS:02d}-{b*N_BLOCK_HRS+N_BLOCK_HRS-1:02d}", "n": int(m.sum()),
                "cov_before": round(float(np.mean((y[m] >= lo0[m]) & (y[m] <= hi0[m]))), 4),
                "cov_after": round(float(np.mean((y[m] >= lo1[m]) & (y[m] <= hi1[m]))), 4),
                "width_before": round(float(np.mean(hi0[m] - lo0[m])), 3),
                "width_after": round(float(np.mean(hi1[m] - lo1[m])), 3),
                "mean_radius": round(float(np.mean(per_block_radius[name][int(b)])), 3) if per_block_radius[name][int(b)] else None,
            }
        out[name] = {"nominal": 1 - alpha, "n": int(y.size),
                     "cov_before": round(cov0, 4), "cov_after": round(cov1, 4),
                     "width_before": round(w0, 3), "width_after": round(w1, 3),
                     "per_block": per_block}
    return out

def main():
    fr, _ = ds.build_hub_frame("HB_HOUSTON")
    # reuse Task-6 tuned params (consistency); fall back to tune() if the file is absent
    params = None
    mrp = os.path.join(OUT_DIR, "model_result.json")
    if os.path.exists(mrp):
        params = json.load(open(mrp))["hubs"]["HB_HOUSTON"]["tuning"]["chosen"]
    if not params:
        params, _ = M.tune(fr)
    print("params:", params, flush=True)
    splits = sp.walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
    ev = [s for s in splits if s.test_start >= M.TUNE_END]
    print(f"conformal over {len(ev)} eval folds, cal_days={CAL_DAYS}, {24//N_BLOCK_HRS} hour-blocks", flush=True)
    res = run_conformal(fr, ev, params)
    report = {"kind": "dart_conformal", "stamp": mx.stamp(), "hub": "HB_HOUSTON",
              "cal_days": CAL_DAYS, "n_hour_blocks": 24 // N_BLOCK_HRS, "params": params,
              "method": "split-conformal CQR per hour-block; calibration = last 90d of train (pre-test)",
              "intervals": res}
    mx.write_json(report, os.path.join(OUT_DIR, "conformal_result.json"))
    print("\n==== CONFORMAL CALIBRATION (HB_HOUSTON) ====")
    for name, r in res.items():
        print(f"\n{name}% interval (nominal {r['nominal']:.2f}), n={r['n']}")
        print(f"  coverage  before {r['cov_before']:.3f} -> after {r['cov_after']:.3f}   (target {r['nominal']:.2f})")
        print(f"  width($)  before {r['width_before']:.2f} -> after {r['width_after']:.2f}")
        print(f"  {'block':6s} {'cov_before':>10s} {'cov_after':>9s} {'w_before':>8s} {'w_after':>7s}")
        for b, pb in r["per_block"].items():
            print(f"  {pb['hours']:6s} {pb['cov_before']:>10.3f} {pb['cov_after']:>9.3f} {pb['width_before']:>8.2f} {pb['width_after']:>7.2f}")
    print("\nwrote conformal_result.json")

if __name__ == "__main__":
    main()
