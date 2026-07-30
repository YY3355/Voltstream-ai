"""Task 5 — baselines through the harness, end-to-end (walk-forward, real numbers).

Three first-class baselines (constraint 4), evaluated on pooled out-of-sample walk-forward test rows:
  * zero_spread : predict dart = 0 (DA == RT). All quantiles 0; spike prob 0.
  * persistence : predict the freshest clean same-hour DART (dart_persist, = Dg-2 same hour). Point
                  forecast used for all quantiles; spike prob = 1{persist < -T} (hard).
  * climatology : PER-FOLD, TRAIN-ONLY month-hour DART quantiles + empirical spike prob (reuses the
                  desk_climatology (month,hour) binning convention + min_samples rule, but recomputed
                  on each fold's TRAIN slice — NOT the leaky full-decade snapshot). The real
                  probabilistic baseline.

Climatology is train-only per fold precisely because the committed clim_result.json snapshot spans the
whole decade (incl. test periods) and would be lookahead. See PROGRESS.md T4 note.

Honesty: HB_HOUSTON runs the full 89-fold monthly walk-forward (the headline). NORTH/SOUTH/WEST have
only ~28 days of paired RT -> a single small holdout, small-sample label, NEVER averaged with Houston.
No LLM. Reads only the assembled frames. Writes research/dart_forecast/baselines_result.json + plots.
"""
from __future__ import annotations
import os, sys, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as ds, splitter as sp, metrics as mx

MIN_SAMPLES = 30   # desk_climatology convention: below this a cell is insufficient -> fall back
OUT_DIR = os.path.join(ds.REPO, "research/dart_forecast")

# ----------------------------- per-fold train-only climatology -----------------------------
def fold_climatology(train_df: pd.DataFrame, taus=mx.TAUS, T=mx.SPIKE_T, min_samples=MIN_SAMPLES):
    d = pd.DataFrame({"dart": train_df["dart"].values,
                      "m": train_df.index.month, "h": train_df.index.hour})
    cell_q, cell_spike = {}, {}
    for (m, h), s in d.groupby(["m", "h"])["dart"]:
        if len(s) >= min_samples:
            cell_q[(m, h)] = {t: float(np.quantile(s, t)) for t in taus}
            cell_spike[(m, h)] = float((s < -T).mean())
    g_q = {t: float(np.quantile(d["dart"], t)) for t in taus}          # fallback (all train)
    g_spike = float((d["dart"] < -T).mean())
    return {"cell_q": cell_q, "cell_spike": cell_spike, "g_q": g_q, "g_spike": g_spike, "taus": taus}

def climatology_predict(clim, test_df: pd.DataFrame):
    m = test_df.index.month.values; h = test_df.index.hour.values
    n = len(test_df)
    qp = {t: np.empty(n) for t in clim["taus"]}
    sp_ = np.empty(n)
    for i in range(n):
        key = (int(m[i]), int(h[i]))
        cq = clim["cell_q"].get(key)
        for t in clim["taus"]:
            qp[t][i] = (cq[t] if cq else clim["g_q"][t])
        sp_[i] = clim["cell_spike"].get(key, clim["g_spike"])
    return qp, sp_

# ----------------------------- baseline predictors -----------------------------
def predict_baselines(train_df, test_df, taus=mx.TAUS, T=mx.SPIKE_T):
    n = len(test_df)
    out = {}
    # zero-spread
    out["zero_spread"] = {"q": {t: np.zeros(n) for t in taus}, "spike_p": np.zeros(n)}
    # persistence (point -> all quantiles; hard spike indicator)
    persist = test_df["dart_persist"].values.astype(float)
    out["persistence"] = {"q": {t: persist.copy() for t in taus},
                          "spike_p": (persist < -T).astype(float)}
    # climatology (train-only, per fold)
    clim = fold_climatology(train_df, taus, T)
    qp, sp_ = climatology_predict(clim, test_df)
    out["climatology"] = {"q": qp, "spike_p": sp_}
    return out

# ----------------------------- walk-forward runner (pooled OOS) -----------------------------
def run_hub(hub, frame, splits, taus=mx.TAUS, T=mx.SPIKE_T):
    pooled = {b: {"q": {t: [] for t in taus}, "spike_p": [], "y": []}
              for b in ("zero_spread", "persistence", "climatology")}
    for s in splits:
        tr = frame.iloc[s.train_pos]; te = frame.iloc[s.test_pos]
        y = te["dart"].values
        preds = predict_baselines(tr, te, taus, T)
        for b, p in preds.items():
            for t in taus:
                pooled[b]["q"][t].append(p["q"][t])
            pooled[b]["spike_p"].append(p["spike_p"])
            pooled[b]["y"].append(y)
    results = {}
    for b, acc in pooled.items():
        y = np.concatenate(acc["y"])
        qp = {t: np.concatenate(acc["q"][t]) for t in taus}
        sp_ = np.concatenate(acc["spike_p"])
        qres = mx.evaluate_quantiles(y, qp, taus)
        spres = mx.evaluate_spike(y, sp_, T)
        results[b] = {"n": int(y.size), "quantiles": qres, "spike": spres}
    return results

def small_hub_split(frame, frac_train=0.5):
    """Single chronological holdout for RT-limited hubs (~28d). Small-sample; not vs Houston."""
    n = len(frame); k = int(n * frac_train)
    tr = frame.iloc[:k]; te = frame.iloc[k:]
    from types import SimpleNamespace
    return SimpleNamespace(train_pos=np.arange(k), test_pos=np.arange(k, n),
                           train_start=tr.index.min(), train_end=tr.index.max(),
                           test_start=te.index.min(), test_end=te.index.max(),
                           n_train=k, n_test=n-k, fold_id=0)

# ----------------------------- plots -----------------------------
def plot_baselines(hub, results, taus, path):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    colors = {"zero_spread": "#888", "persistence": "#58a6ff", "climatology": "#3fb950"}
    for b, r in results.items():
        pins = [r["quantiles"]["pinball"][f"{t:.2f}"] for t in taus]
        ax[0].plot([int(t*100) for t in taus], pins, "o-", label=b, color=colors.get(b))
        cov = [r["quantiles"]["coverage_below"][f"{t:.2f}"] for t in taus]
        ax[1].plot([int(t*100) for t in taus], cov, "o-", label=b, color=colors.get(b))
    ax[0].set(title=f"{hub}: pinball loss by quantile (lower=better)", xlabel="quantile", ylabel="pinball ($/MWh)")
    ax[1].plot([10,25,50,75,90],[.10,.25,.50,.75,.90],"k--",lw=1,label="nominal")
    ax[1].set(title=f"{hub}: coverage (P[y<=q]) vs nominal", xlabel="quantile", ylabel="empirical coverage")
    for a in ax: a.legend(fontsize=8); a.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
    return path

# ----------------------------- main -----------------------------
def main():
    da, rt, clim = ds.load_da_hourly(), ds.load_rt_hourly(), ds.load_clim()
    report = {"kind": "dart_baselines", "stamp": mx.stamp(),
              "climatology_note": "PER-FOLD train-only (month,hour) quantiles; NOT the full-decade snapshot",
              "hub_order": ds.HUBS, "small_sample": {}, "spans": {}, "methods": {}, "hubs": {}}
    methods = {}
    for hub in ds.HUBS:
        fr, meta = ds.build_hub_frame(hub, da, rt, clim)
        if fr is None or len(fr) < 60:
            report["hubs"][hub] = {"status": "insufficient", "n": 0 if fr is None else len(fr)}
            continue
        small = hub != "HB_HOUSTON"
        report["small_sample"][hub] = small
        if not small:
            splits = sp.walk_forward_splits(fr.index, embargo_days=1, min_train_days=365)
            scheme = f"walk-forward, {len(splits)} monthly folds, embargo 1d"
        else:
            splits = [small_hub_split(fr)]
            scheme = "single 50/50 chronological holdout (small sample — NOT comparable to Houston)"
        res = run_hub(hub, fr, splits, mx.TAUS, mx.SPIKE_T)
        report["hubs"][hub] = {"status": "ok", "small_sample": small, "scheme": scheme,
                               "n_test": sum(int(s.n_test) for s in splits),
                               "span": [str(fr.index.min()), str(fr.index.max())],
                               "rt_coverage": meta.get("rt_coverage"),
                               "drop_counts": meta.get("drop_counts"), "results": res}
        report["spans"][hub] = f"{str(fr.index.min())[:10]}..{str(fr.index.max())[:10]}"
        for b, r in res.items():
            methods.setdefault(b, {})[hub] = {"n": r["n"], "quantiles": r["quantiles"], "spike": r["spike"]}
        if not small:
            p = plot_baselines(hub, res, mx.TAUS, os.path.join(OUT_DIR, f"baselines_{hub}.png"))
            report["hubs"][hub]["plot"] = os.path.basename(p)
    report["methods"] = methods
    report["small_sample_note"] = ("HB_NORTH/SOUTH/WEST: ~28-day RT coverage, single holdout, "
                                    "small-sample — NEVER averaged into a headline with Houston.")
    mx.write_json(report, os.path.join(OUT_DIR, "baselines_result.json"))
    mx.write_markdown(report, os.path.join(OUT_DIR, "baselines_report.md"),
                      title="DART forecast — baseline results (walk-forward, no model yet)")
    # console table (Houston headline)
    print("\n==== BASELINE RESULTS (pooled out-of-sample) ====")
    for hub in ds.HUBS:
        h = report["hubs"].get(hub, {})
        if h.get("status") != "ok":
            print(f"{hub}: {h.get('status')}"); continue
        print(f"\n{hub}  [{h['scheme']}]  n_test={h['n_test']}  span={report['spans'][hub]}"
              + ("   *** SMALL SAMPLE ***" if h["small_sample"] else ""))
        print(f"  {'baseline':12s} {'meanPin':>8s} " + " ".join(f"q{int(t*100):>2d}" for t in mx.TAUS)
              + f" {'10-90cov':>8s} {'spkBrier':>8s} {'spkBase':>7s}")
        for b, r in h["results"].items():
            q = r["quantiles"]; s = r["spike"]
            pins = " ".join(f"{q['pinball'][f'{t:.2f}']:5.2f}" for t in mx.TAUS)
            print(f"  {b:12s} {q['pinball_mean']:8.3f} {pins} {q['interval_coverage_10_90']:8.3f} "
                  f"{s['brier']:8.4f} {s['base_rate']:7.4f}")
    print("\nwrote baselines_result.json + baselines_report.md + plots")

if __name__ == "__main__":
    main()
