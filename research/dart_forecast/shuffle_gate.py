"""Task 8 — SHUFFLED-TARGET GATE (statistical leakage backstop).

Retrain the EXACT model pipeline per fold, but with the TRAINING targets PERMUTED (features untouched,
test targets real). Shuffling destroys every feature->target relationship, so a non-leaking pipeline
can only recover the UNCONDITIONAL marginal of the shuffled targets -> it must NOT beat the climatology
baseline out-of-sample. If the shuffled-target model DOES beat climatology, some feature leaks the
target (or train/test contamination exists) regardless of declared provenance (this is the backstop the
Task-3 guard defers to). In that case the gate FAILS and the loop STOPS as blocked.

Deterministic: per-fold permutation seeded by SEED+fold_id. Reuses the T6 model + tuned params.
No LLM. Writes research/dart_forecast/shuffle_gate_result.json and asserts the gate (exit 1 if leaked).
"""
from __future__ import annotations
import os, sys, json, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx, baselines as bl, model as M

OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")
SEED = 42
TOL = 0.02   # shuffled may not be more than 2% BETTER than climatology (noise band); below that = leak

def run_gate(frame, splits, params, taus=mx.TAUS, log_every=15):
    pool = {m: {t: [] for t in taus} for m in ("shuffled", "climatology")}
    y_all = []
    t0 = time.time()
    for i, s in enumerate(splits):
        tr = frame.iloc[s.train_pos]; te = frame.iloc[s.test_pos]
        y = te["dart"].values; y_all.append(y)
        cf_tr, cf_te = M.add_fold_clim(tr, te)          # features from REAL train (we test the features)
        Xtr, Xte = M._xy(tr, cf_tr), M._xy(te, cf_te)
        # PERMUTE the fit target only (deterministic per fold)
        rng = np.random.RandomState(SEED + s.fold_id)
        y_shuf = tr["dart"].values[rng.permutation(len(tr))]
        qm = M.fit_quantiles(Xtr, y_shuf, params)
        qp = M.predict_quantiles(qm, Xte)
        for t in taus:
            pool["shuffled"][t].append(qp[t])
        cpred = bl.predict_baselines(tr, te, taus, mx.SPIKE_TS)["climatology"]
        for t in taus:
            pool["climatology"][t].append(cpred["q"][t])
        if log_every and (i % log_every == 0 or i == len(splits) - 1):
            print(f"  fold {i+1}/{len(splits)} test={s.test_start.date()} ({time.time()-t0:.0f}s)", flush=True)
    y = np.concatenate(y_all)
    res = {}
    for m in ("shuffled", "climatology"):
        qp = {t: np.concatenate(pool[m][t]) for t in taus}
        res[m] = mx.evaluate_quantiles(y, qp, taus)
    return res

def main():
    fr, _ = ds.build_hub_frame("HB_HOUSTON")
    mr = json.load(open(os.path.join(OUT_DIR, "model_result.json")))["hubs"]["HB_HOUSTON"]
    params = mr["tuning"]["chosen"]
    real_model_pin = mr["results"]["model"]["quantiles"]["pinball_mean"]
    splits = sp.walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
    ev = [s for s in splits if s.test_start >= M.TUNE_END]
    print(f"shuffled-target gate over {len(ev)} eval folds (seed {SEED}+fold)", flush=True)
    res = run_gate(fr, ev, params)
    shuf, clim = res["shuffled"]["pinball_mean"], res["climatology"]["pinball_mean"]
    # GATE: shuffled must NOT beat climatology (allow TOL noise band). beats => leak => blocked.
    beats = shuf < clim * (1 - TOL)
    verdict = "LEAK — BLOCKED" if beats else "PASS (shuffled does not beat climatology)"
    report = {"kind": "dart_shuffle_gate", "stamp": mx.stamp(), "hub": "HB_HOUSTON",
              "n_eval_folds": len(ev), "n": res["shuffled"]["n"], "tol": TOL,
              "shuffled_mean_pinball": round(shuf, 4), "climatology_mean_pinball": round(clim, 4),
              "real_model_mean_pinball": round(real_model_pin, 4),
              "shuffled_vs_clim_pct": round(100 * (shuf - clim) / clim, 2),
              "real_vs_clim_pct": round(100 * (real_model_pin - clim) / clim, 2),
              "shuffled_per_q": res["shuffled"]["pinball"], "clim_per_q": res["climatology"]["pinball"],
              "gate_pass": (not beats), "verdict": verdict}
    mx.write_json(report, os.path.join(OUT_DIR, "shuffle_gate_result.json"))
    print("\n==== SHUFFLED-TARGET GATE (HB_HOUSTON) ====")
    print(f"  shuffled-target model mean pinball : {shuf:.4f}")
    print(f"  climatology baseline  mean pinball : {clim:.4f}   (shuffled is {report['shuffled_vs_clim_pct']:+.1f}% vs clim)")
    print(f"  REAL model            mean pinball : {real_model_pin:.4f}   ({report['real_vs_clim_pct']:+.1f}% vs clim)")
    print(f"  VERDICT: {verdict}")
    # hard assertion — the gate
    assert not beats, (f"SHUFFLED-TARGET GATE FAILED: shuffled ({shuf:.4f}) beats climatology "
                       f"({clim:.4f}) by >{TOL:.0%} -> pipeline leaks. STOP (blocked).")
    print("\nGATE PASSED — shuffled targets cannot beat the climatology baseline (no detectable leak).")
    print("wrote shuffle_gate_result.json")

if __name__ == "__main__":
    main()
