"""Task 9 — calibration + results plots (from the committed result JSONs).

Reads model_result.json / conformal_result.json / baselines_result.json and writes PNGs:
  fig_pinball_vs_baseline.png   pinball by quantile, model vs climatology (+ Δ%)
  fig_coverage_pit.png          empirical coverage P(y<=q) vs nominal, model vs climatology
  fig_spike_reliability.png     reliability diagrams for the $20 and $100 spike heads (model vs clim)
  fig_conformal_blocks.png      80% interval coverage before/after conformal, per hour-block
Every plotted point comes straight from a JSON field (checker matches two points against the JSON).
"""
from __future__ import annotations
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
TAUS = [0.10, 0.25, 0.50, 0.75, 0.90]
QX = [int(t*100) for t in TAUS]
C = {"model": "#22d3ee", "climatology": "#3fb950", "nominal": "#888", "before": "#f0a35e", "after": "#22d3ee"}

def load(name):
    return json.load(open(os.path.join(HERE, name)))

def fig_pinball(model_j):
    h = model_j["hubs"]["HB_HOUSTON"]; res = h["results"]; dlt = h["delta_vs_climatology"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for m in ("climatology", "model"):
        pin = [res[m]["quantiles"]["pinball"][f"{t:.2f}"] for t in TAUS]
        ax.plot(QX, pin, "o-", label=f"{m} (mean {res[m]['quantiles']['pinball_mean']:.2f})", color=C[m], lw=2)
    for t in TAUS:
        d = dlt["pinball_pct"][f"{t:.2f}"]
        ax.annotate(f"{d:+.0f}%", (int(t*100), res["model"]["quantiles"]["pinball"][f"{t:.2f}"]),
                    textcoords="offset points", xytext=(0, -14), ha="center", fontsize=8,
                    color="#c9302c" if d > 0 else "#2e7d32")
    ax.set(title=f"HB_HOUSTON pinball by quantile — model Δ {dlt['pinball_mean_pct']:+.1f}% vs climatology "
                 f"(n={res['model']['n']}, 2020–2026)", xlabel="quantile", ylabel="pinball loss ($/MWh)")
    ax.legend(); ax.grid(alpha=.3); ax.set_xticks(QX)
    return _save(fig, "fig_pinball_vs_baseline.png")

def fig_coverage(model_j):
    res = model_j["hubs"]["HB_HOUSTON"]["results"]
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot([0, 100], [0, 1], "--", color=C["nominal"], label="nominal (calibrated)")
    for m in ("climatology", "model"):
        cov = [res[m]["quantiles"]["coverage_below"][f"{t:.2f}"] for t in TAUS]
        ax.plot(QX, cov, "o-", label=f"{m} (10–90 cov {res[m]['quantiles']['interval_coverage_10_90']:.2f})",
                color=C[m], lw=2)
    ax.set(title="HB_HOUSTON coverage P(y ≤ q) vs nominal (pre-conformal)",
           xlabel="quantile", ylabel="empirical coverage"); ax.legend(); ax.grid(alpha=.3); ax.set_xticks(QX)
    return _save(fig, "fig_coverage_pit.png")

def fig_spike(model_j):
    res = model_j["hubs"]["HB_HOUSTON"]["results"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    for j, T in enumerate(("20", "100")):
        a = ax[j]; a.plot([0, 1], [0, 1], "--", color=C["nominal"], label="perfect")
        for m in ("climatology", "model"):
            rel = res[m]["spike"][T]["reliability"]
            xs = [b["mean_pred"] for b in rel if b["mean_pred"] is not None and b["n"] > 0]
            ys = [b["emp_freq"] for b in rel if b["mean_pred"] is not None and b["n"] > 0]
            a.plot(xs, ys, "o-", label=f"{m} (LL {res[m]['spike'][T]['log_loss']:.2f})", color=C[m])
        base = res["climatology"]["spike"][T]["base_rate"]; nev = res["climatology"]["spike"][T]["n_events"]
        a.set(title=f"Spike ${T}/MWh reliability (base {base:.3f}, {nev} events)",
              xlabel="predicted P(RT−DA>${})".format(T), ylabel="empirical frequency")
        a.legend(fontsize=8); a.grid(alpha=.3)
    fig.suptitle("HB_HOUSTON spike-head reliability — model vs climatology", y=1.02)
    return _save(fig, "fig_spike_reliability.png")

def fig_conformal(conf_j):
    r = conf_j["intervals"]["80"]; pb = r["per_block"]
    blocks = sorted(pb, key=int); labels = [pb[b]["hours"] for b in blocks]
    before = [pb[b]["cov_before"] for b in blocks]; after = [pb[b]["cov_after"] for b in blocks]
    x = np.arange(len(blocks)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(x - w/2, before, w, label=f"before (overall {r['cov_before']:.2f})", color=C["before"])
    ax.bar(x + w/2, after, w, label=f"after (overall {r['cov_after']:.2f})", color=C["after"])
    ax.axhline(r["nominal"], ls="--", color="k", lw=1, label=f"nominal {r['nominal']:.2f}")
    ax.set(title="HB_HOUSTON 80% interval coverage by hour-block — split-conformal (CQR)",
           xlabel="hour-block (CT)", ylabel="empirical coverage", ylim=(0, 1))
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.legend(fontsize=8); ax.grid(alpha=.3, axis="y")
    return _save(fig, "fig_conformal_blocks.png")

def _save(fig, name):
    fig.tight_layout(); p = os.path.join(HERE, name); fig.savefig(p, dpi=115, bbox_inches="tight")
    plt.close(fig); return name

def main():
    model_j = load("model_result.json"); conf_j = load("conformal_result.json")
    made = [fig_pinball(model_j), fig_coverage(model_j), fig_spike(model_j), fig_conformal(conf_j)]
    print("wrote:", ", ".join(made))

if __name__ == "__main__":
    main()
