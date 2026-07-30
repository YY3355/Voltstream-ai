"""Task 4 — metrics + report core (pure, hand-checkable).

Target: dart = DA - RT ($/MWh).  Quantiles evaluated: TAUS = 0.10/0.25/0.50/0.75/0.90.
Spike head: the RT spike above DA, event = (RT - DA > T)  <=>  (dart < -T), T = SPIKE_T ($/MWh).
(Per the GOAL parenthetical "RT exceeding DA by threshold" — the economically painful RT-over-DA
excursion. Stated explicitly so the sign is unambiguous.)

Everything here is a pure function of numpy arrays so it can be hand re-derived by the checker.
No NaN coercion: metric fns require finite inputs (callers drop+count upstream).
"""
from __future__ import annotations
import os, json, subprocess
from datetime import datetime, timezone
import numpy as np

TAUS = [0.10, 0.25, 0.50, 0.75, 0.90]
SPIKE_T = 20.0                 # $/MWh — primary spike head ("RT exceeds DA by >= $20/MWh")
SPIKE_TS = [20.0, 100.0]       # both heads: $20 (common) and $100 (scarcity-adjacent tail — blowup/vega)
MIN_SPIKE_EVENTS = 5           # below this per fold, a Brier/log-loss is hollow -> flag, don't trust it
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ------------------------------- core metrics -------------------------------
def pinball_loss(y_true, q_pred, tau: float) -> float:
    """Mean pinball (quantile) loss at level tau.
       L = mean( tau*(y-q) if y>=q else (1-tau)*(q-y) )."""
    y = np.asarray(y_true, float); q = np.asarray(q_pred, float)
    if y.shape != q.shape:
        raise ValueError("shape mismatch")
    if not (np.isfinite(y).all() and np.isfinite(q).all()):
        raise ValueError("non-finite input to pinball_loss (drop+count upstream)")
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1.0) * d)))

def coverage_below(y_true, q_pred) -> float:
    """Empirical P(y <= q) — should approx tau for a well-calibrated quantile."""
    y = np.asarray(y_true, float); q = np.asarray(q_pred, float)
    return float(np.mean(y <= q))

def interval_coverage(y_true, lo_pred, hi_pred) -> float:
    """Empirical P(lo <= y <= hi) — central interval coverage."""
    y = np.asarray(y_true, float); lo = np.asarray(lo_pred, float); hi = np.asarray(hi_pred, float)
    return float(np.mean((y >= lo) & (y <= hi)))

def brier_score(event, p_pred) -> float:
    """Brier score = mean((p - 1{event})^2) for a binary event."""
    e = np.asarray(event, float); p = np.asarray(p_pred, float)
    if not np.isfinite(p).all():
        raise ValueError("non-finite probability")
    return float(np.mean((p - e) ** 2))

def log_loss(event, p_pred, eps: float = 1e-15) -> float:
    """Binary cross-entropy = -mean(e*log p + (1-e)*log(1-p)), p clipped to [eps, 1-eps].
       More sensitive than Brier to confident-wrong tail calls — matters for the rare $100 head."""
    e = np.asarray(event, float); p = np.clip(np.asarray(p_pred, float), eps, 1 - eps)
    return float(-np.mean(e * np.log(p) + (1 - e) * np.log(1 - p)))

# NOTE on spike probabilities: we deliberately do NOT derive P(dart<-T) by interpolating q10..q90 —
# 5 central quantiles cannot resolve the $100 scarcity tail (it would collapse to a near-constant
# ~0.10 and read as informative when it isn't). Every method supplies a DIRECT spike probability:
# climatology = empirical train cell rate P(dart<-T|month,hour); zero_spread = 0; persistence = the
# hard indicator 1{persist<-T}; the model (Task 6) = a dedicated per-threshold tail classifier.

def spike_event(dart, T: float = SPIKE_T) -> np.ndarray:
    """Boolean array: RT spike above DA, dart < -T  (RT - DA > T)."""
    return (np.asarray(dart, float) < -float(T))

def reliability_bins(event, p_pred, n_bins: int = 10):
    """Calibration bins: for each predicted-prob bin, mean predicted vs empirical frequency."""
    e = np.asarray(event, float); p = np.asarray(p_pred, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        n = int(m.sum())
        out.append({"bin": [round(lo, 3), round(hi, 3)], "n": n,
                    "mean_pred": float(p[m].mean()) if n else None,
                    "emp_freq": float(e[m].mean()) if n else None})
    return out

# ------------------------------- per (hub, split) evaluation -------------------------------
def evaluate_quantiles(y_true, q_preds: dict, taus=TAUS) -> dict:
    """q_preds: {tau: array}. Returns pinball per tau, coverage_below per tau, and 10-90 interval cov."""
    y = np.asarray(y_true, float)
    pin = {f"{t:.2f}": pinball_loss(y, q_preds[t], t) for t in taus}
    cov = {f"{t:.2f}": coverage_below(y, q_preds[t]) for t in taus}
    res = {"n": int(y.size), "pinball": pin, "coverage_below": cov,
           "pinball_mean": float(np.mean(list(pin.values())))}
    if 0.10 in q_preds and 0.90 in q_preds:
        res["interval_coverage_10_90"] = interval_coverage(y, q_preds[0.10], q_preds[0.90])
    return res

def evaluate_spike(dart_true, p_spike, T: float = SPIKE_T, n_bins: int = 10,
                   min_events: int = MIN_SPIKE_EVENTS) -> dict:
    ev = spike_event(dart_true, T).astype(float)
    n_ev = int(ev.sum())
    out = {"T": T, "n": int(ev.size), "n_events": n_ev, "base_rate": float(ev.mean()),
           "brier": brier_score(ev, p_spike), "log_loss": log_loss(ev, p_spike),
           "reliability": reliability_bins(ev, p_spike, n_bins)}
    if n_ev < min_events:
        out["low_event_warning"] = f"only {n_ev} events (< {min_events}); Brier/log-loss are hollow here"
    return out

def evaluate_spike_multi(dart_true, p_spike_by_T: dict, Ts=SPIKE_TS, n_bins: int = 10) -> dict:
    """{T: evaluate_spike(...)} for each threshold; p_spike_by_T maps T -> probability array."""
    return {f"{T:.0f}": evaluate_spike(dart_true, p_spike_by_T[T], T, n_bins) for T in Ts}

def fold_event_counts(dart_true_by_fold, Ts=SPIKE_TS) -> dict:
    """Per-fold event counts per threshold, flagging folds below MIN_SPIKE_EVENTS."""
    rep = {}
    for T in Ts:
        counts = [int(spike_event(y, T).sum()) for y in dart_true_by_fold]
        rep[f"{T:.0f}"] = {"per_fold_counts": counts, "total": int(sum(counts)),
                           "folds_below_min": int(sum(c < MIN_SPIKE_EVENTS for c in counts)),
                           "n_folds": len(counts)}
    return rep

# ------------------------------- report writers -------------------------------
def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "UNKNOWN"

def stamp(span=None, n=None, seed=42, extra=None) -> dict:
    s = {"git_sha": git_sha(), "generated_at": datetime.now(timezone.utc).isoformat(),
         "seed": seed, "span": span, "n_samples": n, "target": "dart = DA - RT ($/MWh)",
         "taus": TAUS, "spike_T": SPIKE_T}
    if extra:
        s.update(extra)
    return s

def write_json(obj: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, default=str)
    return path

def _fmt(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))

def write_markdown(report: dict, path: str, title: str = "DART forecast — results"):
    """report: {"stamp":..., "methods": {method: {hub: {"quantiles":..., "spike":..., "n":..., "span":...}}}}"""
    L = [f"# {title}", ""]
    st = report.get("stamp", {})
    L += [f"- git SHA: `{st.get('git_sha','?')}`  · seed: {st.get('seed')}  · generated: {st.get('generated_at','')}",
          f"- target: **{st.get('target','dart = DA - RT')}**  · quantiles: {st.get('taus')}  · spike T: ${st.get('spike_T')}/MWh",
          f"- ⚠ {report.get('small_sample_note','')}" if report.get('small_sample_note') else "", ""]
    for hub in report.get("hub_order", sorted({h for m in report.get("methods", {}).values() for h in m})):
        L += [f"## {hub}" + ("  _(small sample — never averaged with Houston)_" if report.get("small_sample", {}).get(hub) else ""), ""]
        L += ["| method | n | mean pinball | " + " | ".join(f"pin q{int(t*100)}" for t in TAUS)
              + " | 10–90 cov | spike Brier | spike base |", "|" + "---|" * (5 + len(TAUS) + 1)]
        for method, hubs in report.get("methods", {}).items():
            r = hubs.get(hub)
            if not r:
                continue
            q = r.get("quantiles", {}); sp = r.get("spike", {})
            pins = " | ".join(_fmt(q.get("pinball", {}).get(f"{t:.2f}")) for t in TAUS)
            L.append(f"| {method} | {r.get('n','—')} | {_fmt(q.get('pinball_mean'))} | {pins} | "
                     f"{_fmt(q.get('interval_coverage_10_90'))} | {_fmt(sp.get('brier'))} | {_fmt(sp.get('base_rate'),3)} |")
        L += ["", f"_span: {report.get('spans',{}).get(hub,'—')}_", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return path


if __name__ == "__main__":
    # self-test: hand values
    y = np.array([1.0, 2.0, 3.0, 4.0]); q = np.array([2.0, 2.0, 2.0, 2.0])
    # tau=0.5: |y-q|/2 mean = (1+0+1+2)/2 /4 = 4/2/4 = 0.5
    assert abs(pinball_loss(y, q, 0.5) - 0.5) < 1e-12, pinball_loss(y, q, 0.5)
    # tau=0.9, d=y-q=[-1,0,1,2]: max(.9d, -.1d) = [.1,0,.9,1.8]; mean=2.8/4=0.7
    assert abs(pinball_loss(y, q, 0.9) - 0.7) < 1e-12, pinball_loss(y, q, 0.9)
    # coverage_below(q=2): y<=2 -> [T,T,F,F] = 0.5
    assert abs(coverage_below(y, q) - 0.5) < 1e-12
    # brier: event=[0,0,1,1], p=[0,0,1,1] -> 0 ; p=0.5 -> 0.25
    assert abs(brier_score(np.array([0,0,1,1]), np.array([.5,.5,.5,.5])) - 0.25) < 1e-12
    # log_loss: e=[0,1], p=0.5 -> -mean(log .5)= ln2 = 0.6931
    assert abs(log_loss(np.array([0,1]), np.array([.5,.5])) - np.log(2)) < 1e-9
    # log_loss perfect -> ~0 ; confidently-wrong -> large (clipped)
    assert log_loss(np.array([1,0]), np.array([1-1e-15,1e-15])) < 1e-6
    assert list(spike_event(np.array([-25.0, -10.0, 5.0]), 20.0)) == [True, False, False]
    # $100 head: dart<-100
    assert list(spike_event(np.array([-120.0, -50.0]), 100.0)) == [True, False]
    print("metrics self-test PASSED (pinball q50=0.5,q90=0.7; cov=0.5; brier=0.25; logloss=ln2; spike $20/$100 ok)")
