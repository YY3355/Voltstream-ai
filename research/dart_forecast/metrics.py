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
SPIKE_T = 20.0          # $/MWh — "RT exceeds DA by >= $20/MWh" spike head (stated in code)
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

def evaluate_spike(dart_true, p_spike, T: float = SPIKE_T, n_bins: int = 10) -> dict:
    ev = spike_event(dart_true, T).astype(float)
    return {"T": T, "base_rate": float(ev.mean()), "brier": brier_score(ev, p_spike),
            "reliability": reliability_bins(ev, p_spike, n_bins)}

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
    assert list(spike_event(np.array([-25.0, -10.0, 5.0]), 20.0)) == [True, False, False]
    print("metrics self-test PASSED (pinball q50=0.5, q90=0.7; coverage=0.5; brier=0.25; spike ok)")
