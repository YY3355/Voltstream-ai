"""Task 10 — economic overlay (LABELED, hypothetical, small-sample).

Feeds the model's central DART forecast (q50) through a COPY of the live signal rule and compares the
hypothetical P&L to the SAME rule driven by baseline inputs (climatology q50; trailing-bias proxy).
This is NOT a backtest of a tradeable strategy — see the CAVEATS block below.

Signal rule (copied from dart_journal.py — NOT imported, the live file is untouched):
  position(bias) = +1 if bias > THRESH else -1 if bias < -THRESH else 0   (THRESH = 1.0 $/MWh)
  pnl = position * realized_dart   (1 MW, 1 hour; dart = DA - RT; +1 = sell DA/buy RT, profits if DA rich)

Only the q50 (median) regressor is fit per fold (the rule needs a central point forecast), over the
same 2020-2026 eval folds as T6. Deterministic. Writes research/dart_forecast/overlay_result.json.
"""
from __future__ import annotations
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx, baselines as bl, model as M

OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")
THRESH = 1.0   # $/MWh — copied from dart_journal.build_calls (THRESH), live file untouched
INCUMBENT = {"days": 12, "pnl": 1577.23, "hit_rate_pct": 53.9}   # real paper book, for CONTEXT only

def position(bias, thresh=THRESH):
    return np.where(bias > thresh, 1, np.where(bias < -thresh, -1, 0))

def _summ(pos, realized):
    pnl = pos * realized                       # 1 MW, 1 h
    taken = pos != 0
    prof = (pnl > 0) & taken
    return {"total_pnl": round(float(pnl.sum()), 2), "n_hours": int(len(pos)),
            "n_positions": int(taken.sum()),
            "pnl_per_position": round(float(pnl[taken].mean()), 4) if taken.any() else 0.0,
            "hit_rate_pct": round(100 * float(prof.sum() / taken.sum()), 1) if taken.any() else None,
            "long_frac": round(float((pos > 0).mean()), 3), "short_frac": round(float((pos < 0).mean()), 3)}

def run_overlay(frame, splits, params, q50_alpha=0.50, sample_date=None, log_every=20):
    inputs = ("model", "climatology", "trailing")
    acc = {k: {"pos": [], "real": []} for k in inputs}
    sample = None
    t0 = time.time()
    for i, s in enumerate(splits):
        tr = frame.iloc[s.train_pos]; te = frame.iloc[s.test_pos]
        real = te["dart"].values
        cf_tr, cf_te = M.add_fold_clim(tr, te)
        Xtr, Xte = M._xy(tr, cf_tr), M._xy(te, cf_te)
        # model q50 only (the rule needs a central point forecast)
        q50 = M.fit_quantiles(Xtr, tr["dart"].values, params, taus=[q50_alpha])
        model_bias = M.predict_quantiles(q50, Xte, taus=[q50_alpha])[q50_alpha]
        clim_bias = bl.predict_baselines(tr, te, [q50_alpha], mx.SPIKE_TS)["climatology"]["q"][q50_alpha]
        trail_bias = te["dart_trail7_mean"].values   # incumbent-style trailing hour-of-day bias (7d proxy)
        biases = {"model": model_bias, "climatology": clim_bias, "trailing": trail_bias}
        for k in inputs:
            b = np.where(np.isfinite(biases[k]), biases[k], 0.0)   # missing bias -> no position (0)
            acc[k]["pos"].append(position(b)); acc[k]["real"].append(real)
        if sample_date is not None and sample is None:
            mask = te.index.normalize() == pd.Timestamp(sample_date)
            if mask.any():
                sample = {"date": str(sample_date), "fold_test_start": str(s.test_start),
                          "hours": [int(h) for h in te.index.hour[mask]],
                          "realized_dart": [round(float(x), 4) for x in real[mask]],
                          "model_bias": [round(float(x), 4) for x in np.asarray(model_bias)[mask]],
                          "model_position": [int(x) for x in position(np.asarray(model_bias)[mask])],
                          "model_pnl": [round(float(p*r), 4) for p, r in
                                        zip(position(np.asarray(model_bias)[mask]), real[mask])]}
                sample["model_day_pnl"] = round(float(sum(sample["model_pnl"])), 4)
        if log_every and (i % log_every == 0 or i == len(splits) - 1):
            print(f"  fold {i+1}/{len(splits)} ({time.time()-t0:.0f}s)", flush=True)
    res = {}
    for k in inputs:
        pos = np.concatenate(acc[k]["pos"]); real = np.concatenate(acc[k]["real"])
        res[k] = _summ(pos, real)
    return res, sample

def main():
    fr, _ = ds.build_hub_frame("HB_HOUSTON")
    params = json.load(open(os.path.join(OUT_DIR, "model_result.json")))["hubs"]["HB_HOUSTON"]["tuning"]["chosen"]
    splits = sp.walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
    ev = [s for s in splits if s.test_start >= M.TUNE_END]
    sample_date = "2023-08-15"     # a mid-sample day for the hand-check
    print(f"economic overlay over {len(ev)} eval folds (rule THRESH=${THRESH})", flush=True)
    res, sample = run_overlay(fr, ev, params, sample_date=sample_date)
    span = [str(ev[0].test_start), str(ev[-1].test_end)]
    report = {"kind": "dart_economic_overlay", "stamp": mx.stamp(span=span), "hub": "HB_HOUSTON",
              "rule": f"position=sign(bias) if |bias|>{THRESH} else 0; pnl=position*realized_dart (1 MW,1h)",
              "rule_source": "COPIED from dart_journal.build_calls/score_calls (THRESH=1.0); live file untouched",
              "span": span, "n_eval_folds": len(ev), "inputs": res, "sample_day": sample,
              "CAVEATS": [
                  "HYPOTHETICAL — virtual fills at settlement; NO execution, NO fees, NO slippage, NO risk limits.",
                  "1 MW hour clips; single hub (HB_HOUSTON); a research overlay, NOT a tradeable backtest.",
                  "Model drives per-day/hour positions; climatology per (month,hour); trailing is a 7d hour-of-day proxy of the live 10d bias.",
                  f"CONTEXT only (do NOT compare directly): the live paper book = +${INCUMBENT['pnl']} over "
                  f"{INCUMBENT['days']} days @ {INCUMBENT['hit_rate_pct']}% — different period, scale, and construction.",
                  "No statistical-significance claims. Reported as Δ hypothetical P&L between rule inputs only."]}
    mx.write_json(report, os.path.join(OUT_DIR, "overlay_result.json"))
    print("\n==== ECONOMIC OVERLAY (HB_HOUSTON, HYPOTHETICAL) ====")
    print(f"span {span[0][:10]}..{span[1][:10]}  n_hours={res['model']['n_hours']}  rule THRESH=${THRESH}")
    print(f"  {'input':12s} {'total_pnl':>10s} {'n_pos':>6s} {'pnl/pos':>8s} {'hit%':>6s} {'long':>5s} {'short':>5s}")
    for k in ("trailing", "climatology", "model"):
        r = res[k]
        print(f"  {k:12s} {r['total_pnl']:>10.1f} {r['n_positions']:>6d} {r['pnl_per_position']:>8.3f} "
              f"{r['hit_rate_pct']:>6.1f} {r['long_frac']:>5.2f} {r['short_frac']:>5.2f}")
    print(f"\n  [CONTEXT ONLY] live paper book +${INCUMBENT['pnl']} / {INCUMBENT['days']}d @ {INCUMBENT['hit_rate_pct']}% "
          f"— different period/scale/construction; not comparable.")
    if sample:
        print(f"  sample day {sample['date']}: model day P&L ${sample['model_day_pnl']} ({len(sample['hours'])} hours)")
    print("wrote overlay_result.json")

if __name__ == "__main__":
    main()
