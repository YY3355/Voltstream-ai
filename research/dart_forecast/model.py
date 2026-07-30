"""Task 6 — LightGBM quantile models per hub (Houston first-class).

Design:
  * One LightGBM regressor per quantile (objective="quantile", alpha=tau), 5 per fold.
  * Dedicated binary spike classifiers (objective="binary") per threshold, per fold — the DIRECT tail
    estimator (5 central quantiles can't resolve the $100 head).
  * Features: price DA(D+1) curve + lag/trailing + calendar + PER-FOLD TRAIN-ONLY climatology
    quantiles. The STATIC clim_result.json columns are EXCLUDED (full-decade snapshot = lookahead).
  * Walk-forward, MONTHLY retrain (same splitter). Hyperparameters tuned on an inner chronological
    validation carved from a PRE-2020 tuning block; evaluation uses only folds with test_start>=2020,
    so tuning data never overlaps any test fold (checker audits this).
  * Determinism: num_threads=1, deterministic=True, force_row_wise=True, fixed seed -> re-run identical.
  * Quantile crossing fixed by per-row sort (rearrangement).
  * Results reported as Δ vs climatology (recomputed on the SAME eval folds) per Mike's framing rule.

Needs the libomp symlink (macOS): ln -sf $CONDA/lib/libomp.dylib $CONDA/envs/volt/lib/libomp.dylib
No LLM. Reads only assembled frames + committed stores. Writes research/dart_forecast/model_result.json + plots.
"""
from __future__ import annotations
import os, sys, json, time
import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx, baselines as bl

OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")
TUNE_END = pd.Timestamp("2020-01-01")   # tuning uses data strictly before this; eval folds start >= this
SEED = 42

# static clim columns are the leaky full-decade snapshot -> excluded from model inputs
STATIC_CLIM = ["clim_q05", "clim_q25", "clim_q50", "clim_q75", "clim_q95", "clim_dart_mean", "clim_p_da_gt_rt"]
BASE_FEATURES = ["da", "da_day_mean", "da_day_max", "da_day_min", "da_day_range",
                 "dart_persist", "dart_lag48", "dart_lag72", "dart_lag168",
                 "dart_trail7_mean", "dart_trail7_std", "dart_trail30_mean",
                 "rt_trail7_mean", "rt_trail7_std",
                 "hour", "dow", "month", "is_weekend", "hour_sin", "hour_cos", "doy_sin", "doy_cos"]
FOLD_CLIM_FEATURES = ["cf_q10", "cf_q25", "cf_q50", "cf_q75", "cf_q90"]   # per-fold train-only clim
MODEL_FEATURES = BASE_FEATURES + FOLD_CLIM_FEATURES

BASE_PARAMS = dict(verbose=-1, num_threads=1, deterministic=True, force_row_wise=True,
                   seed=SEED, bagging_freq=0, feature_fraction=1.0, min_child_samples=50)
GRID = [dict(num_leaves=nl, learning_rate=lr, n_estimators=ne)
        for nl in (15, 31) for lr in (0.03, 0.05) for ne in (400,)]   # modest, tuned on inner val only

# ----------------------------- feature prep -----------------------------
def add_fold_clim(train_df, test_df):
    """Per-fold TRAIN-ONLY climatology quantiles appended as features (cf_q10..cf_q90)."""
    clim = bl.fold_climatology(train_df, taus=mx.TAUS, Ts=mx.SPIKE_TS)
    out = {}
    for name, df in (("tr", train_df), ("te", test_df)):
        qp, _ = bl.climatology_predict(clim, df)
        cf = pd.DataFrame({f"cf_q{int(t*100):02d}": qp[t] for t in mx.TAUS}, index=df.index)
        out[name] = cf
    return out["tr"], out["te"]

def _xy(frame_slice, cf):
    X = pd.concat([frame_slice[BASE_FEATURES], cf], axis=1)[MODEL_FEATURES]
    return X

# ----------------------------- fit / predict -----------------------------
def fit_quantiles(X, y, params, taus=mx.TAUS):
    models = {}
    for t in taus:
        p = {**BASE_PARAMS, **{k: v for k, v in params.items() if k != "n_estimators"},
             "objective": "quantile", "alpha": t}
        models[t] = lgb.train(p, lgb.Dataset(X, label=y), num_boost_round=params["n_estimators"])
    return models

def predict_quantiles(models, X, taus=mx.TAUS):
    preds = np.stack([models[t].predict(X) for t in taus], axis=1)   # (n, k)
    preds = np.sort(preds, axis=1)                                    # fix quantile crossing (rearrange)
    return {t: preds[:, i] for i, t in enumerate(taus)}

def fit_spike(X, dart_y, params, Ts=mx.SPIKE_TS):
    models = {}
    for T in Ts:
        yb = (dart_y < -T).astype(int)
        p = {**BASE_PARAMS, **{k: v for k, v in params.items() if k != "n_estimators"},
             "objective": "binary"}
        # if a fold's train has no positive spike events, fall back to constant base rate
        if yb.sum() == 0:
            models[T] = ("const", 0.0)
        else:
            models[T] = ("lgb", lgb.train(p, lgb.Dataset(X, label=yb), num_boost_round=params["n_estimators"]))
    return models

def predict_spike(models, X, Ts=mx.SPIKE_TS):
    out = {}
    for T in Ts:
        kind, m = models[T]
        out[T] = np.full(len(X), m) if kind == "const" else m.predict(X)
    return out

# ----------------------------- tuning (inner validation, pre-2020 only) -----------------------------
def tune(frame, tune_end=TUNE_END):
    tdf = frame[frame.index < tune_end]
    k = int(len(tdf) * 0.8)
    inner_tr, inner_val = tdf.iloc[:k], tdf.iloc[k:]
    cf_tr, cf_val = add_fold_clim(inner_tr, inner_val)
    Xtr, Xval = _xy(inner_tr, cf_tr), _xy(inner_val, cf_val)
    ytr, yval = inner_tr["dart"].values, inner_val["dart"].values
    best, best_score = None, np.inf
    scores = []
    for params in GRID:
        models = fit_quantiles(Xtr, ytr, params)
        qp = predict_quantiles(models, Xval)
        mean_pin = np.mean([mx.pinball_loss(yval, qp[t], t) for t in mx.TAUS])
        scores.append({**params, "val_mean_pinball": round(float(mean_pin), 5)})
        if mean_pin < best_score:
            best_score, best = mean_pin, params
    return best, {"tune_span": [str(tdf.index.min()), str(tdf.index.max())],
                  "inner_val_span": [str(inner_val.index.min()), str(inner_val.index.max())],
                  "grid_scores": scores, "chosen": best, "chosen_val_mean_pinball": round(float(best_score), 5)}

# ----------------------------- walk-forward evaluation -----------------------------
def run_model(hub, frame, splits, params, taus=mx.TAUS, Ts=mx.SPIKE_TS, log_every=10):
    # pooled model + climatology (recomputed on the SAME eval folds -> apples-to-apples Delta)
    pool = {m: {"q": {t: [] for t in taus}, "sp": {T: [] for T in Ts}, "y": []}
            for m in ("model", "climatology")}
    per_fold_y = []
    t0 = time.time()
    for i, s in enumerate(splits):
        tr = frame.iloc[s.train_pos]; te = frame.iloc[s.test_pos]
        y = te["dart"].values; per_fold_y.append(y)
        cf_tr, cf_te = add_fold_clim(tr, te)
        Xtr, Xte = _xy(tr, cf_tr), _xy(te, cf_te)
        # model
        qm = fit_quantiles(Xtr, tr["dart"].values, params)
        sm = fit_spike(Xtr, tr["dart"].values, params)
        qp = predict_quantiles(qm, Xte); spk = predict_spike(sm, Xte)
        for t in taus: pool["model"]["q"][t].append(qp[t])
        for T in Ts: pool["model"]["sp"][T].append(spk[T])
        pool["model"]["y"].append(y)
        # climatology on the SAME fold (from baselines)
        cpreds = bl.predict_baselines(tr, te, taus, Ts)["climatology"]
        for t in taus: pool["climatology"]["q"][t].append(cpreds["q"][t])
        for T in Ts: pool["climatology"]["sp"][T].append(cpreds["spike_p"][T])
        pool["climatology"]["y"].append(y)
        if log_every and (i % log_every == 0 or i == len(splits) - 1):
            print(f"  fold {i+1}/{len(splits)} test={s.test_start.date()} ({time.time()-t0:.0f}s)", flush=True)
    results = {}
    for m, acc in pool.items():
        y = np.concatenate(acc["y"])
        qp = {t: np.concatenate(acc["q"][t]) for t in taus}
        spmulti = {T: np.concatenate(acc["sp"][T]) for T in Ts}
        results[m] = {"n": int(y.size), "quantiles": mx.evaluate_quantiles(y, qp, taus),
                      "spike": mx.evaluate_spike_multi(y, spmulti, Ts)}
    return results, mx.fold_event_counts(per_fold_y, Ts)

def delta_vs_clim(model_res, clim_res, taus=mx.TAUS, Ts=mx.SPIKE_TS):
    """Δ% (negative = model better). pinball per quantile + mean; spike Brier/log-loss per head."""
    d = {"pinball_pct": {}, "spike_brier_pct": {}, "spike_logloss_pct": {}}
    mp, cp = model_res["quantiles"]["pinball"], clim_res["quantiles"]["pinball"]
    for t in taus:
        k = f"{t:.2f}"
        d["pinball_pct"][k] = round(100 * (mp[k] - cp[k]) / cp[k], 2)
    d["pinball_mean_pct"] = round(100 * (model_res["quantiles"]["pinball_mean"]
                                         - clim_res["quantiles"]["pinball_mean"]) / clim_res["quantiles"]["pinball_mean"], 2)
    for T in Ts:
        k = f"{T:.0f}"
        mb, cb = model_res["spike"][k]["brier"], clim_res["spike"][k]["brier"]
        ml, cl = model_res["spike"][k]["log_loss"], clim_res["spike"][k]["log_loss"]
        d["spike_brier_pct"][k] = round(100 * (mb - cb) / cb, 2) if cb else None
        d["spike_logloss_pct"][k] = round(100 * (ml - cl) / cl, 2) if cl else None
    return d

def main():
    da, rt, clim = ds.load_da_hourly(), ds.load_rt_hourly(), ds.load_clim()
    report = {"kind": "dart_lgbm_model", "stamp": mx.stamp(),
              "model_features": MODEL_FEATURES, "excluded_static_clim": STATIC_CLIM,
              "params_base": {k: v for k, v in BASE_PARAMS.items()},
              "tuning_rule": "grid tuned on inner val within pre-2020 block; eval folds test_start>=2020",
              "hubs": {}}
    hub = "HB_HOUSTON"   # first-class; small hubs handled separately (too thin to model — Task 6 note)
    fr, meta = ds.build_hub_frame(hub, da, rt, clim)
    best, tune_info = tune(fr)
    print("tuned:", best, "val_mean_pinball", tune_info["chosen_val_mean_pinball"], flush=True)
    splits = sp.walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
    eval_splits = [s for s in splits if s.test_start >= TUNE_END]
    print(f"eval folds: {len(eval_splits)} (test_start >= {TUNE_END.date()}), retrain monthly", flush=True)
    res, evc = run_model(hub, fr, eval_splits, best)
    dlt = delta_vs_clim(res["model"], res["climatology"])
    report["hubs"][hub] = {"status": "ok", "span_eval": [str(eval_splits[0].test_start), str(eval_splits[-1].test_end)],
                           "n_eval_folds": len(eval_splits), "n_test": res["model"]["n"],
                           "tuning": tune_info, "results": res, "delta_vs_climatology": dlt,
                           "spike_event_counts": evc}
    report["small_hub_note"] = ("HB_NORTH/SOUTH/WEST have ~28d paired RT — too thin to train a "
                                "walk-forward model; they remain baselines/climatology only (constraint 5).")
    mx.write_json(report, os.path.join(OUT_DIR, "model_result.json"))
    # console
    print("\n==== LightGBM model vs climatology (HB_HOUSTON, same eval folds) ====")
    print(f"eval: {report['hubs'][hub]['span_eval']}  n={res['model']['n']}  folds={len(eval_splits)}")
    for m in ("climatology", "model"):
        q = res[m]["quantiles"]
        print(f"  {m:11s} meanPin {q['pinball_mean']:7.3f}  10-90cov {q['interval_coverage_10_90']:.3f}  "
              + " ".join(f"q{int(t*100)}={q['pinball'][f'{t:.2f}']:.2f}" for t in mx.TAUS))
    print(f"  Δ vs clim: mean pinball {dlt['pinball_mean_pct']:+.1f}%  per-q "
          + " ".join(f"q{int(t*100)}={dlt['pinball_pct'][f'{t:.2f}']:+.1f}%" for t in mx.TAUS))
    for T in mx.SPIKE_TS:
        k = f"{T:.0f}"
        print(f"  spike ${int(T)}: model Brier {res['model']['spike'][k]['brier']:.4f} LL {res['model']['spike'][k]['log_loss']:.3f}"
              f" | clim Brier {res['climatology']['spike'][k]['brier']:.4f} LL {res['climatology']['spike'][k]['log_loss']:.3f}"
              f" | ΔLL {dlt['spike_logloss_pct'][k]:+.1f}%  events={evc[k]['total']} ({evc[k]['folds_below_min']}/{evc[k]['n_folds']} folds<5)")
    print("\nwrote model_result.json")

if __name__ == "__main__":
    main()
