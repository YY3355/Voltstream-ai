"""Task 7 support — extract the honest OOS confidence band for a plan date, from the walk-forward fold
whose TEST window contains that date (the fold whose model was trained ONLY on data before the test
cutoff). This is decision-time-clean: the band is what the model actually would have said, not the final
model looking back at its own training period.

Pipeline (same discipline as model.py + conformal.py):
  1. find the fold with test_start <= date < test_end.
  2. split its train into proper-train + calibration (last CAL_DAYS); fit quantile + spike models on
     proper-train (tuned params); conformal-calibrate per hour-block on calibration.
  3. predict the date's 24 hourly DART quantiles OOS; apply the per-hour-block conformal radius.
  4. RT band = DA - DART with the quantile FLIP (RT decreasing in DART): rt_q10 = DA - dart_q90, etc.
  5. spike head P(RT-DA > $100) for the evening hours, from the fold's spike classifier.
Writes research/dart_forecast/band_<date>.json (COMMIT it — the frontend serves the committed artifact).

Run: conda run -n volt python research/dart_forecast/make_band.py 2026-05-18
"""
from __future__ import annotations
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx, model as M, conformal as C

OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")
SPIKE_T = 100.0            # scarcity-adjacent tail: P(RT - DA > $100)
EVENING = range(18, 24)    # "tonight" = hours 18:00-23:00

def build_band(date_str: str):
    date = pd.Timestamp(date_str)
    fr, _ = ds.build_hub_frame("HB_HOUSTON")
    params = json.load(open(os.path.join(OUT_DIR, "model_result.json")))["hubs"]["HB_HOUSTON"]["tuning"]["chosen"]
    splits = sp.walk_forward_splits(fr.index)
    fold = next(s for s in splits if s.test_start <= date < s.test_end + pd.Timedelta(days=1))
    tr = fr.iloc[fold.train_pos]
    cut = tr.index.max() - pd.Timedelta(days=C.CAL_DAYS)
    ptr, cal = tr[tr.index < cut], tr[tr.index >= cut]
    day = fr.iloc[fold.test_pos]; day = day[day.index.normalize() == date].sort_index()
    if not len(day) or day.index.max() >= date + pd.Timedelta(days=1) and False:
        raise SystemExit(f"no rows for {date_str} in the fold test window")

    # ---- fit quantile models on proper-train, predict calibration + the target day (OOS) ----
    cf_ptr, cf_cal = M.add_fold_clim(ptr, cal)
    _, cf_day = M.add_fold_clim(ptr, day)
    Xptr, Xcal, Xday = M._xy(ptr, cf_ptr), M._xy(cal, cf_cal), M._xy(day, cf_day)
    qm = M.fit_quantiles(Xptr, ptr["dart"].values, params)
    qcal, qday = M.predict_quantiles(qm, Xcal), M.predict_quantiles(qm, Xday)

    # ---- per-hour-block conformal radii from calibration (CQR), applied to the day's quantiles ----
    yb_cal = cal["dart"].values; blk_cal = C.hour_block(cal.index.hour); blk_day = C.hour_block(day.index.hour)
    adj = {t: qday[t].copy() for t in mx.TAUS}
    for name, (lo, hi, alpha) in C.INTERVALS.items():
        E = np.maximum(qcal[lo] - yb_cal, yb_cal - qcal[hi])
        radii = {int(b): C.conformal_radius(E[blk_cal == b], alpha) for b in np.unique(blk_cal)}
        gr = C.conformal_radius(E, alpha)
        Qd = np.array([radii.get(int(b), gr) for b in blk_day])
        adj[lo] = adj[lo] - Qd; adj[hi] = adj[hi] + Qd
    # enforce monotone dart quantiles after adjustment
    stack = np.sort(np.stack([adj[t] for t in mx.TAUS], axis=1), axis=1)
    dq = {t: stack[:, i] for i, t in enumerate(mx.TAUS)}

    # ---- RT band = DA - DART, with the quantile FLIP (RT is decreasing in DART) ----
    da = day["da"].values
    rt_band = {"rt_q10": (da - dq[0.90]), "rt_q25": (da - dq[0.75]), "rt_q50": (da - dq[0.50]),
               "rt_q75": (da - dq[0.25]), "rt_q90": (da - dq[0.10])}
    rt_settled = (day["da"].values - day["dart"].values)   # realized RT (research frame)

    # ---- spike head P(RT-DA > $100) for the evening, from the fold's spike classifier ----
    sm = M.fit_spike(Xptr, ptr["dart"].values, params, Ts=[SPIKE_T])
    p_spike_day = M.predict_spike(sm, Xday, Ts=[SPIKE_T])[SPIKE_T]
    ev_mask = np.array([h in EVENING for h in day.index.hour])
    p_evening = float(np.mean(p_spike_day[ev_mask])) if ev_mask.any() else None

    out = {
        "kind": "dart_confidence_band", "date": date_str, "hub": "HB_HOUSTON",
        "model_version": mx.git_sha()[:12], "conformal": True,
        "fold": {"test_start": str(fold.test_start), "train_end": str(tr.index.max()),
                 "cal_start": str(cal.index.min()), "note": "OOS: model trained only before the test window"},
        "generated_from": "walk-forward fold OOS predictions (NOT the final model on its own train period)",
        "hours": [h.strftime("%H:%M") for h in day.index],
        "da": [round(float(x), 2) for x in da],
        "rt_settled": [round(float(x), 2) for x in rt_settled],
        **{k: [round(float(x), 2) for x in v] for k, v in rt_band.items()},
        "spike": {"threshold": SPIKE_T, "event": "RT - DA > $100", "p_evening": None if p_evening is None else round(p_evening, 4),
                  "evening_hours": "18:00-23:00"},
        "label": "forecast band — research model v{sha} · plan solves on point price",
    }
    out["label"] = f"forecast band — research model {out['model_version']} · plan solves on point price"
    return out

if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-05-18"
    band = build_band(date_str)
    dst = os.path.join(OUT_DIR, f"band_{date_str}.json")
    json.dump(band, open(dst, "w"), indent=2)
    n = len(band["hours"])
    print(f"date {date_str}  fold test_start {band['fold']['test_start'][:10]}  train_end {band['fold']['train_end'][:10]} (OOS)")
    print(f"  rt_q50 range ${min(band['rt_q50'])}..${max(band['rt_q50'])}  band q10-q90 width@peak "
          f"${round(max(b-a for a,b in zip(band['rt_q10'],band['rt_q90'])),1)}")
    print(f"  P(RT-DA>$100) evening = {band['spike']['p_evening']}")
    print(f"  wrote {dst}")
